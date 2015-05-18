#!/usr/local/bin/python -u
# RMap_Harvest.py

# See this page for DataCite: http://oai.datacite.org

__author__ = 'timmo'
logging_config_file = 'config/logging.conf'
logging_logger_name = 'rmapLogger'

# get us some stderr handling, at least
import time
import logging
import logging.config
# todo: fix logging
logging.config.fileConfig(logging_config_file)
"""
logging.Formatter.converter = time.gmtime
logging.basicConfig(level=logging.DEBUG,
                    format='|'.join( ('%(asctime)s', '%(process)d', '%(levelname)s',
                                     '[%(module)s %(filename)s %(lineno)d]|%(message)s',
                                      )  ),
                    datefmt='%Y-%m-%dT%H:%M:%SZ')
"""
logging.Formatter.converter = time.gmtime
log = logging.getLogger(logging_logger_name if logging_logger_name is not None else __name__)
#log.setLevel(logging.INFO)

import sys
import traceback
import signal
# import faulthandler
# faulthandler.register(signal.SIGUSR1)
import code

import argparse
import re
import config
from sickle import Sickle
from harvester import Harvester
from lxml import etree
from lxml.etree import XSLTApplyError
import rdflib
import urllib
import urlparse
import requests
from rmap_utils import print_count, isodatez
from collections import Counter
import base64
from existdb import ExistDB

# todo: need a resilient way to wait, then restart an aborted process, including errors related to RMap instance connectivity
# todo: ... and things like this, below...
"""
- If DataCite goes down, we get this exception:
HTTPError: 502 Server Error: Bad Gateway
Traceback (most recent call last):
  File "./RMap_Harvester.py", line 308, in main
    ###################################################
  File "/Users/timmo/Dropbox/JHU/Projects/RMap-Amoeba-MatchMaker-Sloan/dev/Harvesters/harvester.py", line 110, in Event_ListRecords
    for record in iterator: pass
  File "/Users/timmo/Dropbox/JHU/Projects/RMap-Amoeba-MatchMaker-Sloan/dev/Harvesters/harvester.py", line 142, in next
    result = super(OAIIterator, self).next()
  File "/usr/local/lib/python2.7/site-packages/sickle/app.py", line 294, in next
    self._next_response()
  File "/Users/timmo/Dropbox/JHU/Projects/RMap-Amoeba-MatchMaker-Sloan/dev/Harvesters/harvester.py", line 139, in _next_response
    super(OAIIterator, self)._next_response()
  File "/usr/local/lib/python2.7/site-packages/sickle/app.py", line 274, in _next_response
    resumptionToken=self.resumption_token)
  File "/Users/timmo/Dropbox/JHU/Projects/RMap-Amoeba-MatchMaker-Sloan/dev/Harvesters/harvester.py", line 75, in harvest
    response = super(Harvester, self).harvest(**kw)
  File "/usr/local/lib/python2.7/site-packages/sickle/app.py", line 119, in harvest
    http_response.raise_for_status()
  File "/usr/local/lib/python2.7/site-packages/requests/models.py", line 808, in raise_for_status
    raise HTTPError(http_error_msg, response=self)
HTTPError: 502 Server Error: Bad Gateway
ERROR:__main__:Uncaught exception processing OAI-PMH records from baseURL='http://oai.datacite.org/oai' with metadataPrefix='oai_datacite'
"""


#######################################################################
# main ()
#######################################################################


def main():
	# get applicaton properties
	app_config = config.Config('application')

	# get some configuration that we need to handle arguments
	rmap_config = config.Config('rmap')
	repo_config = config.Config('repositories')
	schema_config = config.Config('schemas')

	# handle some arguments
	parser = argparse.ArgumentParser()
	parser.add_argument('-n', '--noharvest', dest='noharvest', default=False, action='store_true')
	parser.add_argument('-t', '--test', dest='test', default=False, action='store_true')
	parser.add_argument('-R', '--rmap', dest='rmap', default='production', help='RMap instance from configuration',
	                    choices=rmap_config.get('rmap_instances').keys() )
	# todo: at some point, the default should be 'all' and we should handle all of the repositories we know about
	parser.add_argument('-r', '--repo', '--repository', dest='repo', default='datacite', help='repository profile',
	                    choices=repo_config.keys())
	parser.add_argument('-s', '--set', default='', dest='set', help='OAI-PMH setSpec')
	# todo: make the default mdprefix "preferred" and add code elsewhere to get the preferred value from the configuration
	parser.add_argument('-m', '--mdprefix', '--mdpfx', dest='mdprefix', default='oai_datacite', help='OAI-PMH metadata prefix',
	                    choices=schema_config.keys())
	parser.add_argument('-k', '--keep', dest='keep', default=False, action='store_true')
	parser.add_argument('-q', '--query', dest='query', default='', help='DataCite MDS query string')
	# todo: might consider implementing these arguments, too
	"""
	- from an optional argument with a UTCdatetime value, which specifies a lower bound for datestamp-based selective harvesting.
	- until an optional argument with a UTCdatetime value, which specifies a upper bound for datestamp-based selective harvesting.
	- resumptionToken
	parser.add_argument('-f', '--from', dest='from', default=None,
	                    help='YYYY-MM-DD optional UTCdatetime value, lower bound for harvesting')
	parser.add_argument('-u', '--until', dest='until', default=None,
	                    help='YYYY-MM-DD optional UTCdatetime value, upper bound for harvesting')
    """
	args = parser.parse_args()


	if args.keep is True:
		# todo: Abstract/generalize! This code assumes that eXist DB is the class for these.
		edb_oai = config_eXistDB(config.Config('persistence')['oai_store'])
		edb_disco = config_eXistDB(config.Config('persistence')['rmap_disco'])
		"""
		# store the OAI record
		edb_oai = ExistDB(persistence_config['oai_store']['endpoint'])
		edb_oai.authenticate(persistence_config['oai_store']['auth']['username'], persistence_config['oai_store']['auth']['password'])
		edb_oai.set_collection(persistence_config['oai_store']['collection'])
		# store the DiSCO
		edb_disco = ExistDB(persistence_config['rmap_store']['endpoint'])
		edb_disco.authenticate(persistence_config['rmap_store']['auth']['username'], persistence_config['oai_store']['auth']['password'])
		edb_disco.set_collection(persistence_config['rmap_store']['collection'])
		"""
	# setup signal handling so we can get stats without terminating
	signal.signal(signal.SIGUSR1, signal_handler)

	# set up XSLT configuration
	xslt_params = {k:etree.XSLT.strparam(v) for (k,v) in app_config.get('xslt').iteritems() }
	xslt_params.update( { 'agent_id': etree.XSLT.strparam( app_config.get('id')) } )
	xslt = {}
	xslt_log = {}
	for schema in schema_config.keys():
		xslt_tree = etree.parse( schema_config.get(schema+':'+'xslt', key_sep=':') )
		xslt[schema] = etree.XSLT( xslt_tree )
		xslt_log[schema] = iter(xslt[schema].error_log)

	# initialize RMAP API request stuff
	rmap_instance_config = rmap_config.get('rmap_instances').get(args.rmap)
	rmap_session = get_rmap_session_from_config(rmap_instance_config)


	# todo: move out of main()
	# todo: would require getting congig, including endpoint
	def rmap_create_disco(disco, session=None,):
		if session is None:
			session = rmap_session # todo: can't rely on this, if we're not in main()
		endpoint = rmap_instance_config['endpoint']
		creation_rel = rmap_config['link_relations.create']
		r = session.post(endpoint+'/disco/', data=disco)
		result = {
			'ok': r.ok,
			'status_code': r.status_code,
			'reason': r.reason,
			'text': r.text,
		}
		# todo: fix encoded event ids, so they don't include the URI
		if r.ok:
			#do some stuff here, based on successful DiSCO creation
			result.update({
			'created_uri': r.text,
			'creation_events': [get_id_from_url(v,urlparse.urlparse(endpoint).path+'/event/')
			                    for (k,v) in r.links[creation_rel].iteritems() if k=='url' ],
			'links': r.links,
			'headers': r.headers,
			})
		return result

	#################
	# deleted_record
	#################
	def deleted_record(record, classes):
		# todo: get disco id from database, encode it, and delete it from RMAP
		# (1) mark it deleted in the database
		# (2) delete (tombstone it in RMap)
		# (3) record tombstone event id in db
		return

	#################
	# active_record
	#################
	def active_record(record):
		errors = 0

		# (1) transform record to DiSCO
		# parameters: record_id=record.header.identifier, record=record, transform=xslt[metadata_prefix],
		#             xslt_params, target_disco_serialization='turtle', error_log_to_return
		# return: turtle, local_error_log
		try:
			# transform record to RMap DiSCO
			xml_tree = etree.XML(record.raw)
			transform = xslt[metadata_prefix]
			try:
				res = transform(xml_tree, **dict( xslt_params.items() +
				                                  {'nowZ': etree.XSLT.strparam(isodatez()),
				                                   'log_id': etree.XSLT.strparam(record.header.identifier),
				                                   }.items()
				                                  ) )

			except etree.XSLTApplyError, e:
				print e.args
			finally:
				#print "****************************"
				entries = get_log_entries(record.header.identifier, transform.error_log, 'ERROR')
				if len(entries) > 0:
					errors += 1
					print "Errors: ", len(entries)
					log.error("%s [%s] record will not be processed", isodatez(), record.header.identifier)
					for entry in entries:
						print entry
						log.error(entry)
					return

			rdfxml = etree.tostring(res, encoding='unicode', method='xml', pretty_print=True, with_comments=True)
			g=rdflib.Graph()
			g.parse(data=rdfxml, format='application/rdf+xml')
			turtle = g.serialize(format='turtle')
			disco =  turtle
			# (2) create db entry
			# (3) create DiSCO in RMap
			r = rmap_create_disco(disco, rmap_session)
			if r['ok']:
				log.info("%s [%s] Created DiSCO [%s] (%s %s): event(s): [%s]",
				             isodatez(), record.header.identifier,
				             r['created_uri'], r['status_code'], r['reason'],
				             ', '.join(r['creation_events']))
			else:
				log.error("%s [%s] Failed to create RMap DiSCO (%s %s): %s",
				              isodatez(), record.header.identifier,
				              r['status_code'], r['reason'], r['text'])
			# (4) record DiSCO creation event in db
			# persist the DiSCO serialization
			if args.keep is True:
				edb_disco.store(disco, record.header.identifier)
		except Exception, e:
			traceback.print_exc()
			log.error('Uncaught exception:"%s"', e.message, exc_info=True)
			log.error(
				"Error processing OAI-PMH record id='%s' from baseURL='%s'",
				record.header.identifier, harvester.endpoint)



	# set up our per-record handler
	def record_handler(obj, element, value):
		if element == 'record':
			record = value
			##################################
			# all records, active and deleted
			##################################
			log.debug("RMap Harvester: element: %s; id: %s%s; rt=[%s]",
			      element, value.header.identifier,
			      ( ' (deleted)' if record.deleted else '' ),
			      ( obj.resumption_token if obj.resumption_token is not None else '(none)' ) )
			"""
			print "\nRMap Harvester: element: %s; id: %s%s; rt=[%s]" % \
			      (element,
			       value.header.identifier,
			       ' (deleted)' if record.deleted else '',
			       obj.resumption_token if obj.resumption_token is not None else '(none)')
			"""

			return

			if args.keep is True:
				edb_oai.store(record.raw, record.header.identifier)

			if record.deleted:
				#################
				# deleted_record
				#################
				deleted_record(record)
			else:
				#################
				# active_record
				#################
				active_record(record)
		else:
			# we don't know about anything else, so report it
			log.error("record_handler() unknown element type: '%s'", element)



	# todo: note that from here on out, this stuff might eventually be in a loop or a thread
	# select the harvester configuration
	repository = args.repo
	harvester_config = repo_config[repository]
	oai_pmh_set = set_query_string(repo_config[repository], args.set, args.query)
	metadata_prefix = harvester_config['preferred_metadata_prefix']

	# metadata_prefixes = conf['metadata_prefixes']
	# prefix_strings = metadata_prefixes.keys()
	harvester_endpoint = harvester_config['url']
	harvester = Harvester(harvester_endpoint)
	# initialize some stuff for datacite
	# client_id = harvester.Identify()

	"""
	# DataCite query support
	# support for query subsets
	# PANGAEA:'fq=prefix%3A"10.1594"'; IEEE: q=10.1109*
	"""

	"""
	client_info=dict(
		name=client_id.repositoryName,
		description=client_id.description,
		baseURL=client_id.baseURL,
		earliest=client_id.earliestDatestamp,
		granularity=client_id.granularity,
		protocolVersion=client_id.protocolVersion,
		compression=client_id.compression,
		oai_identifier=client_id.oai_identifier,
		deletedRecord=client_id.deletedRecord,
	)
	"""
	#

	# If running in test mode, drop to interactive shell, then continue running
	if args.test:
		code.interact(local=locals())

	# If running in noharvest mode, exit without harvesting
	if args.noharvest:
		return

	# harvest the records
	try:
		harvester.Event_ListRecords(metadataPrefix=metadata_prefix, set=oai_pmh_set, callback=record_handler)
	except (KeyboardInterrupt, SystemExit):
		sys.exit(1)
	except Exception, e:
		traceback.print_exc()
		print e.args, e.message
		log.error(
			"Uncaught exception processing OAI-PMH records from baseURL='%s' with metadataPrefix='%s'",
			harvester.endpoint, metadata_prefix)
	finally: pass
		#print_stats()

#######################################################################################


#######################################################################
# Functions
#######################################################################

def signal_handler(sig, stack):
	print '%s handling signal %i' % (isodatez(), sig)
	sys.stdout.flush()
	# print_stats()

###################################################
# instantiate an eXistdb object from configuration
###################################################
def config_eXistDB(config):
	db_object = ExistDB(config['endpoint'])
	# edb_oai.authenticate(config['auth']['username'], config['auth']['password'])
	db_object.authenticate(config['auth.username'], config['auth.password'])
	db_object.set_collection(config['collection'])
	return db_object


###################################################
# configure a RMap session from configuration
###################################################
def get_rmap_session_from_config(config):
	s = requests.Session()
	# username = config['auth']['username']
	# password = config['auth']['password']
	username = config['auth.username']
	password = config['auth.password']
	# if config['auth']['type'].lower() == 'basic':
	if config['auth.type'].lower() == 'basic':
		s.auth = requests.auth.HTTPBasicAuth(username, password)
	else:
		s.auth = (username, password)
	s.headers.update({'content-type': 'text/turtle'})
	return s


###################################################
# get XSLT transform.error_log entries for record_id
###################################################
def get_log_entries(record_id, error_log, level=None):
	pattern = re.escape('['+record_id+']')
	result = [ e.message for e in error_log if re.search(pattern, e.message)]
	if level is not None:
		if level == 'DEBUG': levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'FATAL']
		elif level == 'INFO': levels = ['INFO', 'WARNING', 'ERROR', 'FATAL']
		elif level == 'WARNING': levels = ['WARNING', 'ERROR', 'FATAL']
		elif level == 'ERROR': levels = ['ERROR', 'FATAL']
		if levels is not None:
			pattern =  '|'.join(levels)
		else:
			pattern = level
		result = [ entry for entry in result if re.search(pattern, entry)]
	return result


###################################################
# make a set string that includes encoded query
###################################################
def set_query_string(repo_config, set_string=None, query_string=None):
	if query_string is not None and repo_config.get('supports_datacite_query_encoding'):
		if set_string is None:
			set_string = ''
		set_string += '~' + base64.b64encode(query_string)
	return set_string


###################################################
# strip off thru path prefix, then url decode it
###################################################
def get_id_from_url(url, prefix):
	i = url.find(prefix)
	if i > 0:
		url = url[i+len(prefix):]
	url = urllib.unquote(url).decode('utf8')
	return url


#######################################################################
# End of Functions
#######################################################################

if __name__ == '__main__':
	main()

