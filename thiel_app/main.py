""" This contains Thiel analysis plots """




from os import read
import px4tools
import numpy as np
import math
import io
import os
import sys
import errno
import base64
from db_entry import *

#import thiel_analysis
from bokeh.io import curdoc,output_file, show
from bokeh.models.widgets import Div
from bokeh.layouts import column
from scipy.interpolate import interp1d

import plotting
from plotted_tables import *
from configured_plots import *
from os.path import dirname, join

from config import *
from helper import *
from leaflet import ulog_to_polyline
from bokeh.models import CheckboxGroup
from bokeh.models import RadioButtonGroup
from bokeh.models.widgets import FileInput
from bokeh.models.widgets import Paragraph

import pandas as pd
import argparse

from bokeh.layouts import column, row
from bokeh.models import ColumnDataSource, PreText, Select
from bokeh.plotting import figure
from bokeh.server.server import Server
from bokeh.themes import Theme
from bokeh.application.handlers import DirectoryHandler


#pylint: disable=cell-var-from-loop, undefined-loop-variable,

DATA_DIR = join(dirname(__file__), 'datalogs')


DEFAULT_FIELDS = ['XY', 'LatLon', 'VxVy']

STANDARD_TOOLS = "pan,wheel_zoom,box_zoom,reset,save"

simname = 'faasimulated.ulg'
realname = 'faareal.ulg'
sim_polarity = 1  # determines if we should reverse the Y data
real_polarity = 1
simx_offset = 0
realx_offset = 0
read_file = True
reverse_sim_data = False
reverse_real_data = False
new_data = True
read_file_local = False
new_real = False
new_sim = False
metric = 'x'
keys = []

sim_reverse_button = RadioButtonGroup(
        labels=["Sim Default", "Reversed"], active=0)
sim_reverse_button.on_change('active', lambda attr, old, new: reverse_sim())
real_reverse_button = RadioButtonGroup(
        labels=["Real Default", "Reversed"], active=0)
real_reverse_button.on_change('active', lambda attr, old, new: reverse_real())

# set up widgets

stats = PreText(text='Thiel Coefficient', width=500)
# datatype = Select(value='XY', options=DEFAULT_FIELDS)


# @lru_cache()
def load_data(filename):
    global keys
    fname = join(DATA_DIR, filename)
    ulog = load_ulog_file(fname)
    data = ulog.data_list
    for d in data:
        data_keys = [f.field_name for f in d.field_data]
        data_keys.remove('timestamp')
        keys.append(data_keys)
    cur_dataset = ulog.get_dataset('vehicle_local_position')
    return cur_dataset


# @lru_cache()
def get_data(simname,realname, metric):
    global new_real, new_sim, read_file_local, realfile, simfile
    print("Now in get_data")
    dfsim = load_data(simname)
    dfreal = load_data(realname)

    if read_file_local:    # replace the datalogs with local ones
        if new_real:
            print("Loading in a new real log")
            dfreal = realfile
            new_real = False
        if new_sim:
            print("Loading in a new sim log")
            dfsim = simfile
            new_sim = False
 
    sim_data = dfsim.data[metric]
    pd_sim = pd.DataFrame(sim_data, columns = ['sim'])
    sim_time = dfsim.data['timestamp']
    pd_time = pd.DataFrame(sim_time, columns = ['time'])
    real_data = dfreal.data[metric]
    pd_real = pd.DataFrame(real_data, columns = ['real'])
    new_data = pd.concat([pd_time,pd_sim, pd_real], axis=1)
    new_data = new_data.dropna()   # remove missing values
    return new_data
    # print(new_data)
    # dfdata = pd.DataFrame(cur_dataset.data) 
    # data = pd.concat([dfsim, dfreal], axis=1)
    # data = data.dropna()   # remove missing values
    # sim_mean = dfsim.y.mean()  # get the average
    # real_mean = dfreal.y.mean()
    # mean_diff = sim_mean - real_mean 
    # data.realy = data.realy + mean_diff # normalize the two
    # data['sim'] = dfsim.x
    # data['simt'] = dfsim.timestamp
    # data['real'] = dfreal.x
    # data['realt'] = dfreal.timestamp


def update(selected=None):
    global read_file, read_file_local, reverse_sim_data, reverse_real_data, new_data, datalog, original_data, new_data, datasource
    if (read_file or read_file_local):
        print("Fetching new data", simname, realname, metric)
        original_data = get_data(simname, realname, metric)
        datalog = copy.deepcopy(original_data)
        datasource.data = datalog
        read_file = False
        read_file_local = False
    print("Sim offset", simx_offset)
    print("Real offset", realx_offset)
    if reverse_sim_data:
        datalog[['sim']] = sim_polarity * original_data['sim']  # reverse data if necessary
        simmax = round(max(datalog[['sim']].values)[0])  # reset the axis scales as appopriate (auto scaling doesn't work)
        simmin = round(min(datalog[['sim']].values)[0])
        datasource.data = datalog
        reverse_sim_data = False
    if reverse_real_data:
        datalog['real'] = real_polarity * original_data['real']
        realmax = round(max(datalog[['real']].values)[0])
        realmin = round(min(datalog[['real']].values)[0])
        datasource.data = datalog
        reverse_real_data = False
    if new_data:
        datasource.data = datalog
        new_data = False


def upload_new_data_real(attr, old, new):
    global read_file_local, new_real, realfile, original_data
    print("one")
    read_file_local = True
    new_real = True
    decoded = base64.b64decode(new)
    tempfile = io.BytesIO(decoded)
    tempfile = ULog(tempfile)
    realfile = tempfile.get_dataset('vehicle_local_position')
    print("Uploading new real file")
    update()

def upload_new_data_sim(attr, old, new):
    global read_file_local, new_sim, simfile
    read_file_local = True
    new_sim = True
    decoded = base64.b64decode(new)
    tempfile = io.BytesIO(decoded)
    tempfile = ULog(tempfile)
    simfile = tempfile.get_dataset('vehicle_local_position')
    print("Uploading new sim file")
    update()

def update_stats(data):
    real = np.array(data['realy'])
    sim = np.array(data['simy'])
    sum1 = 0
    sum2 = 0
    sum3 = 0
    for n in range(len(real)):
        sum1 = sum1 + (real[int(n)]-sim[int(n)])**2
        sum2 = sum2 + real[int(n)]**2
        sum3 = sum3 + sim[int(n)]**2
    sum1 = 1/len(real) * sum1
    sum2 = 1/len(real) * sum2
    sum3 = 1/len(real) * sum3
    sum1 = math.sqrt(sum1)
    sum2 = math.sqrt(sum2)
    sum3 = math.sqrt(sum3)
    TIC = sum1/(sum2 + sum3)
    stats.text = 'Thiel coefficient: ' + str(round(TIC,3))


def reverse_sim():
    global sim_polarity, reverse_sim_data
    if (sim_reverse_button.active == 1): sim_polarity = -1
    else: sim_polarity = 1
    reverse_sim_data = True
    update()

def reverse_real():
    global real_polarity, reverse_real_data
    if (real_reverse_button.active == 1): real_polarity = -1
    else: real_polarity = 1
    reverse_real_data = True
    update()

def change_sim_scale(shift):
    global simx_offset, new_data
    simx_offset = shift
    new_data = True
    update()

def change_real_scale(shift):
    global realx_offset, new_data
    realx_offset = shift
    new_data = True
    update()

def sim_change(attrname, old, new):
    global metric, read_file
    print("Sim change:", new)
    metric = new
    read_file = True
    update()   

def get_thiel_analysis_plots(simname, realname):
    global datalog, original_data,datasource

    additional_links= "<b><a href='/browse2?search=sim'>Load Simulation Log</a> <p> <a href='/browse2?search=real'>Load Real Log</a></b>" 

    datalog = get_data(simname, realname, metric)
    original_data = copy.deepcopy(datalog)

    datatype = Select(value='x', options=keys[3])

    datatype.on_change('value', sim_change)

    intro_text = Div(text="""<H2>Sim/Real Thiel Coefficient Calculator</H2>""",width=800, height=100, align="center")
    choose_field_text = Paragraph(text="Choose a data field to compare:",width=500, height=15)
    links_text = Div(text="<table width='100%'><tr><td><h3>" + "</h3></td><td align='left'>" + additional_links+"</td></tr></table>")

    datasource = ColumnDataSource(data = dict(time=[],sim=[],real=[]))
    datasource.data = datalog

    tools = 'xpan,wheel_zoom,reset'
    
    ts1 = figure(plot_width=1000, plot_height=400, tools=tools, x_axis_type='linear')
    ts1.line('time','sim', source=datasource, line_width=2, color="orange", legend_label="Simulated data")
    ts1.line('time','real', source=datasource, line_width=2, color="blue", legend_label="Real data")
    

    # x_range_offset = (datalog.last_timestamp - datalog.start_timestamp) * 0.05
    # x_range = Range1d(datalog.start_timestamp - x_range_offset, datalog.last_timestamp + x_range_offset)
    # flight_mode_changes = get_flight_mode_changes(datalog)

    # set up layout
    widgets = column(datatype,stats)
    sim_button = column(sim_reverse_button)
    real_button = column(real_reverse_button)
    main_row = row(widgets)
    series = column(ts1, sim_button, real_button)
    layout = column(main_row, series)

    # initialize


    update()
    curdoc().add_root(intro_text)
    curdoc().add_root(links_text)
    curdoc().add_root(choose_field_text)    
    curdoc().add_root(layout)
    curdoc().title = "Flight data"

    #     plots = []

    # return plots

print("Now starting Thiel app")
GET_arguments = curdoc().session_context.request.arguments
simname = join(DATA_DIR, simname)    # this is the default log file to load if you haven't been given another one
realname = join(DATA_DIR, realname)    # this is the default log file to load if you haven't been given another one


if GET_arguments is not None and 'log' in GET_arguments:
    log_args = GET_arguments['log']
    if len(log_args) == 1:
        templog_id = str(log_args[0], 'utf-8')
        if (templog_id.find("sim") != -1):
            log_id = templog_id.replace('sim','')
            print("This is a sim file. New log ID=", log_id)
            ulog_file_name = get_log_filename(log_id)
            simname = os.path.join(get_log_filepath(), ulog_file_name)
        elif (templog_id.find("real") != -1):
            log_id = templog_id.replace('real','')
            print("This is a real file. New log ID=", log_id)
            ulog_file_name = get_log_filename(log_id)
            realname = os.path.join(get_log_filepath(), ulog_file_name)
        else:
            log_id = str(log_args[0], 'utf-8')
            if not validate_log_id(log_id):
                raise ValueError('Invalid log id: {}'.format(log_id))
        print('GET[log]={}'.format(log_id))
        ulog_file_name = get_log_filename(log_id)
get_thiel_analysis_plots(simname, realname)