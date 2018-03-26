import numpy
from pyhaystack.exception import HaystackError

__author__ = 'topsykretts'

# server credentials

server_lookup = {
    "niagara_iot_s1": {
        "implementation": "n4",
        "uri": "http://your_server:port",
        "username": "your_username",
        "password": "your_pass",
        "pint": True
    }
}
import pyhaystack
import hszinc

# get session
server_name = 'niagara_iot_s1'
session = pyhaystack.connect(**server_lookup[server_name])


# method to get histories for the server and range


def get_histories(point_id, rng):
    """
    """
    # getting history as dataframe
    history_op = session.his_read_series(hszinc.Ref(point_id), rng=rng)
    history_op.wait()
    history = history_op.result
    return history

# getting points


def get_points():
    points_op = session.find_entity("his and cur and point")
    points_op.wait()
    points = points_op.result
    return points.keys()

# kafka producer initialization
from kafka import KafkaProducer

kafka_configs = {
    'bootstrap_servers': 'localhost:9092',
    'key_serializer': lambda val: str(val).encode('utf-8'),
    'value_serializer': lambda val: str(val).encode('utf-8'),
    'acks': 'all',
    'retries': 1,
    'linger_ms': 1
}

producer = KafkaProducer(**kafka_configs)

# determining range to read histories
import datetime
import pytz

tz = pytz.utc

to_zinc_dt = lambda dt: "%s.%s%s" % (
    dt.strftime('%Y-%m-%dT%H:%M:%S'),
    '{:03.0f}'.format(dt.microsecond / 1000.0),
    dt.strftime('%z %Z')[:3] + ":" + dt.strftime('%z %Z')[3:]
)
# start = to_zinc_dt(tz.localize(datetime.datetime(2018, 2, 1, 0, 0)))
start = None
import os
from os.path import expanduser
home_dir = expanduser("~")
directory = home_dir + "/.niagara_iot"
if not os.path.exists(directory):
    os.makedirs(directory)

try:
    rng_file = open(directory + "/" + server_name+"_rng_lookup.txt", "r")
    for line in rng_file:
        start = line.rstrip()
        break
except FileNotFoundError:
    start = None

if start is None:
    start = "2018-02-01T00:00:00.000+00:00 UTC"
actual_now = datetime.datetime.now(tz=tz)
record_now = to_zinc_dt(actual_now - datetime.timedelta(minutes=1))
now = to_zinc_dt(actual_now)

print("start = ", start)
print("now = ", now)
print("recorded_now = ", record_now)
rng_file_write = open(directory + "/" + server_name+"_rng_lookup.txt", "w")
rng = start + ", " + now
print("rng = ", rng)
for point_id in get_points():
    try:
        points_his = get_histories(point_id, rng)
    except HaystackError:
        print("No records found for " + point_id + " in time range " + rng)
        points_his = None

    import json
    if points_his is not None:
        print("Sending ", point_id, " Records to Kafka")
        for index, value in points_his.iteritems():
            row_data = {"ts": str(index)}
            if isinstance(value, numpy.bool_):
                if value:
                    val = True
                else:
                    val = False
                row_data["val"] = val
            else:
                row_data["val"] = value
            row_data["pointName"] = point_id
            print(json.dumps(row_data))
            producer.send(server_name, json.dumps(row_data)).get()
        producer.flush()
# there is a delay from niagara server to give histories
rng_file_write.write(record_now)

