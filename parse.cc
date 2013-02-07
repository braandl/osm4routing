#include "parse.h"
#include "cmath"

#include <iostream>
#include <cstring>
#include <boost/unordered_map.hpp>
#define PI 3.1415926535897932384626433832795028841971693993751058

using namespace std;

typedef boost::unordered_map<uint64_t, Node> NodeMapType;


double rad(double deg)
{
    return deg * 3.14159265 / 180;
}

double angle(double lon1, double lat1, double lon2, double lat2, double lon3, double lat3)
{

    // a.x = lat1
    // a.y = lon1
    // ...

    double abx = lat2 - lat1;
    double aby = lon2 - lon1;

    double cbx = lat2 - lat3;
    double cby = lon2 - lon3;

    float dot = (abx * cbx + aby * cby); // dot product
    float cross = (abx * cby - aby * cbx); // cross product

    float alpha = atan2(cross, dot);

    return (int) floor(alpha * 180. / PI + 0.5);
}

double distance(double lon1, double lat1, double lon2, double lat2)
{
    const double r = 6371000;

    return acos( sin( rad(lat1) ) * sin( rad(lat2) ) +
            cos( rad(lat1) ) * cos( rad(lat2) ) * cos( rad(lon2-lon1 ) )
            ) * r;
}

void
start(void * data, const char *el, const char **attr)
{
    Parser * d = (Parser*) data;
    if (strcmp(el, "node") == 0)
    {
        node_t id = 0;
        double lat = 0, lon = 0;
        while (*attr != NULL)
        {
            const char* name = *attr++;
            const char* value = *attr++;

            std::string tag = "test";

            if (strcmp(name, "id") == 0)
            {
                id = atoll(value);
            }
            else if (strcmp(name, "lat") == 0)
            {
                lat = atof(value);
            }
            else if (strcmp(name, "lon") == 0)
            {
                lon = atof(value);
            }
        }
        d->nodes[id] = Node(lon, lat, id);
        d->last_insert = id;
    }

    else if (strcmp(el, "nd") == 0)
    {
        const char* name = *attr++;
        const char* value = *attr++;
        if (strcmp(name, "ref") == 0)
        {
            node_t node_id = atoll(value);
            d->way_nodes.push_back(node_id);
        }
    }

    else if(strcmp(el, "way") == 0)
    {
        d->way_nodes.clear();
        d->ep.reset();
        const char* name = *attr++;
        const char* value = *attr++;
        if( !strcmp(name, "id") == 0 )
        {
            cout << "fuck" << std::endl;
        }
        else
        {
            d->current_way = atoll(value);
        }
        d->ways_count++;
    }

    else if(strcmp(el, "tag") == 0)
    {
        string key;
        while (*attr != NULL)
        {
            const char* name = *attr++;
            const char* value = *attr++;

            if ( strcmp(name, "k") == 0 )
                key = value;
            else if (strcmp(name, "v") == 0 )
            {
                if (strcmp(key.c_str(), "tag") == 0) {
                    d->nodes[static_cast<int>(d->last_insert)].tag = value;
                } else {
                    d->ep.update(key, value);
                }
            }
        }
    }
}

void end(void * data, const char * el)
{
    Parser * d = (Parser*) data;
    if(strcmp(el, "way") == 0)
    {
        if(d->ep.accessible())
        {
            d->ep.normalize();
            vector<node_t>::const_iterator it;
            d->temp_edges << d->ep.foot << " "
                << d->ep.car_direct << " " << d->ep.car_reverse << " "
                << d->ep.bike_direct << " " << d->ep.bike_reverse << " "
                << d->way_nodes.size();
            for(it = d->way_nodes.begin(); it < d->way_nodes.end(); ++it)
            {
                d->nodes[*it].uses++;
                d->temp_edges << " " << *it;
            }
            d->temp_edges << endl;

            d->nodes[d->way_nodes.front()].uses++;
            d->nodes[d->way_nodes.back()].uses++;
        }
    } 
}


Parser::Parser()
{
    temp_edges.open("temp_ways");
    parser = XML_ParserCreate(NULL);
    XML_SetElementHandler(parser, start, end);
//    ios_base::sync_with_stdio(false);
    XML_SetUserData(parser, this);
}

void Parser::read(char * buf, int size, bool end)
{
        if( !XML_Parse(parser, buf, size, end) )
        {
            cerr << XML_ErrorString(XML_GetErrorCode(parser)) <<
                " at line " <<
                XML_GetCurrentLineNumber(parser) << endl;
        }

        if(end)
        {
            XML_ParserFree(parser);
            temp_edges.close();
        }
}

vector<Node> Parser::get_nodes() const
{
    vector<Node> ret;
    ret.reserve(nodes.size()/5); //Simply heuristical...
    for(NodeMapType::const_iterator i = nodes.begin(); i != nodes.end(); ++i)
    {
        if( (*i).second.uses > 1 )
        {
            if ((*i).second.tag != "")
                ret.push_back(Node((*i).second.lon, (*i).second.lat, (*i).second.tag, (*i).first));
            else
                ret.push_back(Node((*i).second.lon, (*i).second.lat, (*i).first));
        }
    }
    return ret;

}

vector<Edge> Parser::get_edges() const
{
    vector<Edge> ret;
    ret.reserve(nodes.size()/5); //Simply heuristical...
    ifstream tmp;
    tmp.open("temp_ways");
    node_t id, source=0;
    stringstream geom;
    geom.precision(10);
    double length = 0, pred_lon = 0, pred_lat = 0, pred_lon2 = 0, pred_lat2 = 0;
    char car_direct, car_rev, foot, bike_direct, bike_rev;
    int nb;
    int edges_inserted = 0;
    double dist = 0;
    double ang = 0;
    Node n;
    string line;


    while(getline(tmp, line))
    {
        stringstream way(line);
        way >> foot >> car_direct >> car_rev >> bike_direct >> bike_rev >> nb;
        for(int i=0; i<nb; i++)
        {
            way >> id;
            n = nodes.at(id);

            if(i == 0)
            {
                geom.str("");
                source = id;
                dist = 0;
                ang = 0;
                pred_lon = 0;
                pred_lat = 0;
                pred_lon2 = 0;
                pred_lat2 = 0;
            }
            else
            {
                dist = distance(n.lon, n.lat, pred_lon, pred_lat);
                ang = angle(n.lon, n.lat, pred_lon, pred_lat, pred_lon2, pred_lat2);
                length += dist;
                if(geom.str() != "")
                    geom << ",";
            }

            pred_lon = n.lon;
            pred_lat = n.lat;

            if (i > 1) {
                pred_lon2 = pred_lon;
                pred_lat2 = pred_lat;
            }

            geom << n.lon << " " << n.lat << " " << dist << " " << ang;
            if( i>0 && n.uses > 1 && id != source)
            {
                ret.push_back(Edge(edges_inserted, source, id, length, car_direct, car_rev, bike_direct, bike_rev, foot, geom.str()));
                edges_inserted++;
                length = 0;
                dist = 0;
                ang = 0;
                geom.str("");
                geom << n.lon << " " << n.lat << " " << dist << " " << ang;
                source = id;
            }
        }
    }

    tmp.close();
    return ret;
}

int Parser::get_osm_nodes() const
{
    return nodes.size();
}

int Parser::get_osm_ways() const
{
    return ways_count;
}
