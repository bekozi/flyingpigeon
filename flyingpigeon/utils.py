import ocgis
from netCDF4 import Dataset

from malleefowl import wpslogging as logging
#import logging
logger = logging.getLogger(__name__)

def local_path(url):
    from urllib2 import urlparse
    url_parts = urlparse.urlparse(url)
    return url_parts.path

def calc_grouping(grouping):
    calc_grouping = ['year'] # default year
    if grouping == 'yr':
        calc_grouping = ['year']
    elif grouping == 'sem':
        calc_grouping = [ [12,1,2], [3,4,5], [6,7,8], [9,10,11], 'unique'] 
    elif grouping == 'ONDJFM':
        calc_grouping = [ [10,11,12,1,2,3], 'unique'] 
    elif grouping == 'AMJJAS':
        calc_grouping = [ [4,5,6,7,8,9], 'unique'] 
    elif grouping == 'DJF':
        calc_grouping = [[12,1,2], 'unique']    
    elif grouping == 'MAM':
        calc_grouping = [[3,4,5], 'unique']    
    elif grouping == 'JJA':
        calc_grouping = [[6,7,8], 'unique']    
    elif grouping == 'SON':
        calc_grouping = [[9,10,11], 'unique']
    elif grouping == 'mon':
        calc_grouping = ['year', 'month']
    elif grouping in ['year', 'month']:
        calc_grouping = [grouping]
    else:
        msg = 'Unknown calculation grouping: %s' % grouping
        logger.error(msg)
        raise Exception(msg)
    return calc_grouping

def drs_filename( nc_file, skip_timestamp=False, skip_format=False ):
    """
    generates filename according to the data reference syntax (DRS).
    
    http://cmip-pcmdi.llnl.gov/cmip5/docs/cmip5_data_reference_syntax.pdf
    https://pypi.python.org/pypi/drslib

    :param nc_file: netcdf file
    :param skip_timestamp: if True then from/to timestamp is not added to the filename
                           (default: False)
    :return: DRS filename
    """
    ds = Dataset(nc_file)
    variable = get_variable(nc_file)

    # CORDEX example: EUR-11_ICHEC-EC-EARTH_historical_r3i1p1_DMI-HIRHAM5_v1_day
    cordex_pattern = "{variable}_{domain}_{driving_model}_{experiment}_{ensemble}_{model}_{version}_{frequency}"
    # CMIP5 example: tas_MPI-ESM-LR_historical_r1i1p1
    cmip5_pattern = "{variable}_{model}_{experiment}_{ensemble}"

    filename = nc_file
    try:
        if ds.project_id == 'CORDEX':
            filename = cordex_pattern.format(
                variable = variable,
                domain = ds.CORDEX_domain,
                driving_model = ds.driving_model_id,
                experiment = ds.experiment_id,
                ensemble = ds.driving_model_ensemble_member,
                model = ds.model_id,
                version = ds.rcm_version_id,
                frequency = ds.frequency)
        elif ds.project_id == 'CMIP5':
            # TODO: attributes missing in netcdf file for name generation?
            filename = cmip5_pattern.format(
                variable = variable,
                model = ds.model_id,
                experiment = ds.experiment,
                ensemble = ds.parent_experiment_rip
                )
        else:
            raise Exception('unknown project %s' % ds.project_id)

        # add from/to timestamp if not skipped
        if skip_timestamp == False:
            from_timestamp, to_timestamp = get_timestamps(nc_file)
            filename = "%s_%s-%s" % (filename, int(from_timestamp), int(to_timestamp))

        # add format extension
        if skip_format == False:
            filename = filename + '.nc'
    except:
        logger.exception('Could not generate DRS filename for %s', nc_file)
    
    return filename

def get_variable(nc_file):
    rd = ocgis.RequestDataset(nc_file)
    return rd.variable

def get_timestamps(nc_file):
    """
    returns from/to timestamp of given netcdf file.
    
    :param nc_file: NetCDF file
    returns tuple (from_timestamp, to_timestamp)
    """
    ds = Dataset(nc_file)
    time_list = ds.variables['time']
    from datetime import datetime, timedelta
    reftime = datetime.strptime('1949-12-01', '%Y-%m-%d')
    from_timestamp = datetime.strftime(reftime + timedelta(days=time_list[0]), '%Y%m%d') 
    to_timestamp = datetime.strftime(reftime + timedelta(days=time_list[-1]), '%Y%m%d')
    return (from_timestamp, to_timestamp)
    
def aggregations(nc_files):
    """
    aggregates netcdf files by experiment. Aggregation examples:
    
    CORDEX: EUR-11_ICHEC-EC-EARTH_historical_r3i1p1_DMI-HIRHAM5_v1_day
    CMIP5:
    We collect for each experiment all files on the time axis:
    200101-200512, 200601-201012, ...

    Time axis is sorted by time.

    :param nc_files: list of netcdf files
    :return: dictonary with key=experiment
    """
    
    aggregations = {}
    for nc_file in nc_files:
        key = drs_filename(nc_file, skip_timestamp=True, skip_format=True)

        # collect files of each aggregation (time axis)
        if aggregations.has_key(key):
            aggregations[key]['files'].append(nc_file)
        else:
            aggregations[key] = dict(files=[nc_file])

    # collect aggregation metadata
    for key in aggregations.keys():
        # sort files by time
        aggregations[key]['files'] = sort_by_time(aggregations[key]['files'])
        # start timestamp of first file
        start, _ = get_timestamps(aggregations[key]['files'][0])
        # end timestamp of last file
        _, end = get_timestamps(aggregations[key]['files'][-1])
        aggregations[key]['from_timestamp'] = start
        aggregations[key]['to_timestamp'] = end
        aggregations[key]['start_year'] = int(start[0:4])
        aggregations[key]['end_year'] = int(end[0:4])
        aggregations[key]['variable'] = get_variable(aggregations[key]['files'][0])
        aggregations[key]['filename'] = "%s_%s-%s.nc" % (key, start, end)
    
    return aggregations

def sort_by_time(resources):
    from ocgis.util.helpers import get_sorted_uris_by_time_dimension
    if type(resources) is list:
        sorted_list = get_sorted_uris_by_time_dimension(resources)
    else:
        sorted_list = [resources]
    return sorted_list

def sort_by_filename(resources , historical_concatination = False ):
  """ Sort a list of files with Cordex conform file names. 
  returns a dictionary with name:list_of_files"""
  from os  import path
  ndic = {}
  for nc in resources:
    #logger.debug('file: %s' % nc)
    p, f = path.split(nc) 
    n = f.split('_')
    bn = '_'.join(n[0:-1])
    if historical_concatination == False: 
      ndic[bn] = [] # iniciate an approriate key with empty list in the dictionary
    if historical_concatination == True:
      if n[3] != 'historical':
        ndic[bn] = []      
  for key in ndic:
    if historical_concatination == False:
      for n in resources:
        if key in n: 
          ndic[key].append(n)
    if historical_concatination == True:
      historical = key.replace('rcp26','historical').replace('rcp45','historical').replace('rcp65','historical').replace('rcp85','historical')
      for n in resources:
        if key in n or historical in n: 
          ndic[key].append(n)     
  return ndic # rndic

def has_variable(resource, variable):
    success = False
    try:
        rd = ocgis.RequestDataset(uri=resource)
        success = rd.variable == variable
    except:
        logger.exception('has_variable failed.')
    return success

def filename_creator(nc_files):
  from os import path , rename
  from ocgis import RequestDataset
  from datetime import datetime, timedelta
  
  if type(nc_files) != list:
    nc_files = list(nc_files)
  newnames = []
  for i in range(len(nc_files)):
    fp ,fn = path.split(nc_files[i])
    # logger.debug('fn_creator for: %s' % fn)
    ds = Dataset(nc_files[i])
    rd = []
    rd = RequestDataset(nc_files[i])
    ts = ds.variables['time']
    reftime = reftime = datetime.strptime('1949-12-01', '%Y-%m-%d')
    st = datetime.strftime(reftime + timedelta(days=ts[0]), '%Y%m%d') 
    en = datetime.strftime(reftime + timedelta(days=ts[-1]), '%Y%m%d') 
    
    if (str(ds.project_id) == 'CMIP5'):
    #day_MPI-ESM-LR_historical_r1i1p1
      var = str(rd.variable)
      frq = str(ds.frequency)
      gmodel = str(ds.model_id)
      exp = str(ds.experiment_id)
      ens = str(ds.parent_experiment_rip)
      filename = var + '_' + str( gmodel + '_' + exp + '_' + ens + '_' + str(int(st)) + '-' + str(int(en)) + '.nc')
        
    elif (str(ds.project_id) == 'CORDEX'):
    #EUR-11_ICHEC-EC-EARTH_historical_r3i1p1_DMI-HIRHAM5_v1_day
      var = str(rd.variable)
      dom = str(ds.CORDEX_domain)
      gmodel = str(ds.driving_model_id)
      exp = str(ds.experiment_id)
      ens = str(ds.driving_model_ensemble_member)
      rmodel = str(ds.model_id)
      ver = str(ds.rcm_version_id)
      frq = str(ds.frequency)
      filename = str(var + '_'+ dom + '_' + gmodel + '_' + exp + '_' + ens + '_' + rmodel + '_' + ver + \
        '_' + frq + '_' + str(int(st)) + '-' + str(int(en)) + '.nc' )
    else:
      filename = fn 
      logger.debug('WPS name forwarded :%s' % ( filename))
      
    ##except Exception as e: 
      #msg = 'Could not define file name for file : %s %s' % ( nc , e )
      #logger.error(msg)
      #outlog = outlog + msg + '\n'
    rename(nc_files[i], path.join(fp, filename ))
    newnames.append(path.join(fp, filename))
    logger.debug('file name generated and renamed :%s' % (len(filename)))
  return newnames    

