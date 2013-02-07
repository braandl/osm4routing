from osm4routing_xml import *
import os
import bz2, gzip
import sys
from optparse import OptionParser
from sqlalchemy import Table, Column, MetaData, Integer, String, Float, SmallInteger, create_engine
from sqlalchemy.orm import mapper, sessionmaker
from geoalchemy import *

class Node(object):
    def __init__(self, id, lon, lat, tag, elevation = 0, the_geom = 0, spatial=False):
        wkt_geom = 'POINT({0} {1})'.format(lon, lat)
        self.original_id = id
        self.lon = lon
        self.lat = lat
        self.tag = tag
        self.elevation = elevation
        if spatial:
            self.the_geom = WKTSpatialElement(wkt_geom)
        else:
            self.the_geom = wkt_geom

class Edge(object):
    def __init__(self, id, source, target, length, car, car_rev, bike, bike_rev, foot, the_geom, spatial=False):
        wkt_geom = 'LINESTRING({0})'.format(the_geom)
        self.id = id
        self.source = source
        self.target = target
        self.length = length
        self.car = car
        self.car_rev = car_rev
        self.bike = bike
        self.bike_rev = bike
        self.foot = foot
        if spatial:
            self.the_geom = WKTSpatialElement(wkt_geom)
        else:
            self.the_geom = wkt_geom


def parse(file, output="csv", edges_name="edges", nodes_name="nodes", output_path=".", separator=",", spatial=False, no_headers=False):
    if not os.path.exists(file):
        raise IOError("File {0} not found".format(file))

    if output != "csv":
        metadata = MetaData()
        if(spatial):
            node_geom = Point(2)
            edge_geom = LineString(2)
        else:
            node_geom = String
            edge_geom = String

        nodes_table = Table(nodes_name, metadata,
                Column('id', Integer, primary_key = True),
                Column('original_id', Integer, index = True),
                Column('elevation', Integer),
                Column('lon', Float, index = True),
                Column('lat', Float, index = True),
                Column('tag', String),
                Column('the_geom', node_geom)
                )
        
        edges_table = Table(edges_name, metadata,
            Column('id', Integer, primary_key=True),
            Column('source', Integer, index=True),
            Column('target', Integer, index=True),
            Column('length', Float),
            Column('car', SmallInteger),
            Column('car_rev', SmallInteger),
            Column('bike', SmallInteger),
            Column('bike_rev', SmallInteger),
            Column('foot', SmallInteger),
            Column('the_geom', edge_geom)
            )

        GeometryDDL(nodes_table)
        GeometryDDL(edges_table)


        engine = create_engine(output)
        metadata.drop_all(engine)
        metadata.create_all(engine) 
        mapper(Node, nodes_table)
        mapper(Edge, edges_table)
        Session = sessionmaker(bind=engine)
        session = Session()

    extension = os.path.splitext(file)[1]
    if extension == '.bz2':
        print "Recognized as bzip2 file"
        f = bz2.BZ2File(file, 'r') 

    elif extension == '.gz':
        print "Recognized as gzip2 file"
        f = gzip.open(file, 'r') 

    else:
        print "Supposing OSM/xml file"
        filesize = os.path.getsize(file)
        f = open(file, 'r') 

    buffer_size = 4096
    p = Parser()
    eof = False

    print "Step 1: reading file {0}".format(file)
    read = 0
    while not eof:
        s = f.read(buffer_size)
        eof = len(s) != buffer_size
        p.read(s, len(s), eof)
        read += len(s)

    print "  Read {0} nodes and {1} ways\n".format(p.get_osm_nodes(), p.get_osm_ways())

    print "Step 2: saving the nodes"
    nodes = p.get_nodes()
    if output == "csv":
        n = open(output_path + '/' + nodes_name + '.csv', 'w')
	if no_headers == False:
            n.write('"node_id"'+separator+'"longitude"'+separator+'"latitude"'+separator+'"tag"\n')

    count = 0
    for node in nodes:
        if output == "csv":
            n.write('{1}{0}{2}{0}{3}{0}{4}\n'.format(separator,node.id, node.lon, node.lat, node.tag))
        else:
            session.add(Node(node.id, node.lon, node.lat, node.tag, spatial=spatial))
        count += 1
    if output == "csv":
        n.close()
    else:
        session.commit()

    print "  Wrote {0} nodes\n".format(count)

    print "Step 3: saving the edges"
    edges = p.get_edges()
    count = 0
    if output == "csv":
        print output_path + '/' + edges_name + '.csv'
        e = open(output_path + '/' + edges_name + '.csv', 'w')
	if no_headers == False:
        	e.write('"edge_id"'+separator+'"source"'+separator+'"target"'+separator+'"length"'+separator+'"car"'+separator+'"car reverse"'+separator+'"bike"'+separator+'"bike reverse"'+separator+'"foot"'+separator+'"WKT"\n')
    for edge in edges:
        if output == "csv":
            e.write('{1}{0}{2}{0}{3}{0}{4}{0}{5}{0}{6}{0}{7}{0}{8}{0}{9}{0}LINESTRING({10})\n'.format(separator, edge.edge_id, edge.source, edge.target, edge.length, edge.car, edge.car_d, edge.bike, edge.bike_d, edge.foot, edge.geom))
        else:
            session.add(Edge(edge.edge_id, edge.source, edge.target, edge.length, edge.car, edge.car_d, edge.bike, edge.bike_d, edge.foot, edge.geom, spatial=spatial))
        count += 1
    if output == "csv":
        e.close()
    else:
        session.commit()
    print "  Wrote {0} edges\n".format(count)

def main():
    usage = """Usage: %prog [options] input_file

input_file must be an OSM/XML file. It can be compressed with gzip (.gz) or bzip2 (.bz2)"""


    parser = OptionParser(usage)
    parser.add_option("-o", "--output", dest="output", default="csv",
            help="""'csv' if you want a simple file,
a connection string to use a database (Example: sqlite:///foo.db postgresql://john@localhost/my_database)
[default: %default]""")
    parser.add_option("-n", "--nodes_name", dest="nodes_name", default="nodes", help="Name of the file or table where nodes are stored [default: %default]")
    parser.add_option("-e", "--edges_name", dest="edges_name", default="edges", help="Name of the file or table where edges are stored [default: %default]")
    parser.add_option("-s", "--spatial", dest="spatial", default=False, action="store_true", help="Is the database spatial? If yes, it creates spatial indexes on the column the_geom. Read about geoalchemy to know what databases are supported (only spatial was tested)")
    parser.add_option("-O", "--output-path", dest="output_path", default=".", help="Path of the csv file where nodes are stored [default: %default]")
    parser.add_option("-S", "--separator", dest="separator", default=",", help="Field separator of the csv file where nodes are stored [default: %default]")
    parser.add_option("-H", "--no-headers", dest="no_headers", default=False, action="store_true", help="Skip header line for the csv file where nodes are stored")
    (options, args) = parser.parse_args()

    if len(args) != 1:
        sys.stderr.write("Wrong number of arguments. Expected 1, got {0}\n".format(len(args)))
        sys.exit(1)

    try:
        parse(args[0], options.output, options.edges_name, options.nodes_name, options.output_path, options.separator, options.spatial, options.no_headers)
    except IOError as e:
        sys.stderr.write("I/O error: {0}\n".format(e))
    except Exception as e:
        sys.stderr.write("Woops... an error occured: {0}\n".format(e))

if __name__ == "__main__":
    main()
