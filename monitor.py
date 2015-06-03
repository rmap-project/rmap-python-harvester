__author__ = 'tim.dilauro@gmail.com'

import logging
_logger = logging.getLogger(__name__)
_logger.debug("Module '%s' loading from '%s'", __name__, __file__)

import datetime
from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import ForeignKey
from sqlalchemy import Table, Column
from sqlalchemy.sql import select, update, bindparam
from sqlalchemy import Integer, String, DateTime, Boolean
from sqlalchemy.exc import OperationalError

from rmap_utils import isodatez
import config

#######################################################################
# Constants / Defaults
#######################################################################
DEFAULT_CONFIG_FILE = "config/default.cfg"
DEFAULT_CREDENTIALS_FILE = "config/credentials.cfg"
DEFAULT_MGR_AUTH_KEY = "sql_mgr"

"""
with engine.begin() as conn:
	conn.execute("blah...")
	conn.execute("blah...")
	#...
"""

#######################################################################
# Functions
#######################################################################

def get_db_metadata():
	metadata = MetaData()
	repository_table = \
		Table('repository', metadata,
		      Column('id', Integer, primary_key=True),
		      Column('endpoint', String(150), index=True),
		      )
	monitor_table = \
		Table('monitor', metadata,
		      Column('id', Integer, primary_key=True),
		      Column('repo_id', Integer, ForeignKey('repository.id')),
		      Column('record_id', String(150), index=True, unique=True),
		      Column('active', Boolean),
		      )
	creation_table = \
		Table('creation', metadata,
		      Column('id', Integer, primary_key=True),
		      Column('monitor_id', Integer, ForeignKey('monitor.id')),
		      Column('disco_id', String(150)),
		      Column('event_id', String(150)),
		      Column('event_date', DateTime),
		      )
	deletion_table = \
		Table('deletion', metadata,
		      Column('id', Integer, primary_key=True),
		      Column('monitor_id', Integer, ForeignKey('monitor.id')),
		      Column('disco_id', String(150)),
		      Column('event_id', String(150)),
		      Column('event_date', DateTime),
		      )
	return metadata


def _get_db_engine(dbtype, database, hostname, user, password, encoding='utf-8'):
	engine = create_engine(dbtype + "://" + user + ":" + password + "@" + hostname + "/" + database,
	                       encoding=encoding, echo=False)
	return engine


def get_monitor_from_config(config):
	mon = {}

	db_metadata = get_db_metadata()
	mon['metadata'] = db_metadata

	# create rmap user and db
	engine = _get_db_engine(config['class'], config['database'], config['hostname'],
	                        config['auth']['username'], config['auth']['password'],
	                        encoding=config['encoding'])
	mon['engine'] = engine

	# create statements that be used throughout the process without being created repeatedly
	statements = {}

	# "repository" table
	repository = db_metadata.tables['repository']
	statements['repository_insert'] = repository.insert()
	statements['repository_select'] = select([repository]).\
		where( repository.c.endpoint == bindparam('endpoint') )

	# "monitor" table
	monitor = db_metadata.tables['monitor']
	statements['monitor_insert'] = monitor.insert()
	statements['monitor_select'] = select([monitor]).\
		where( monitor.c.repo_id == bindparam('repo_id') ).\
		where( monitor.c.record_id == bindparam('record_id') )
	statements['monitor_update'] = update(monitor).\
		where( monitor.c.id == bindparam('monitor_id') ).\
		values( active=bindparam('active') )

	# "creation" table
	creation = db_metadata.tables['creation']
	statements['creation_insert'] = creation.insert()
	statements['creation_select'] = select([creation]).\
		where( creation.c.disco_id == bindparam('disco_id') )

	# "deletion" table
	deletion = db_metadata.tables['deletion']
	statements['deletion_insert'] = deletion.insert()

	statements['active_discos'] = \
		select([repository.c.endpoint,
				monitor.c.record_id, monitor.c.active,
				creation.c.disco_id, creation.c.event_id, creation.c.event_date],).\
			select_from(repository.outerjoin(monitor.outerjoin(creation))).\
			where(monitor.c.active).\
			where(monitor.c.record_id == bindparam('record_id')).\
			where(repository.c.endpoint == bindparam('endpoint'))

	# add the statements to the monitor object
	mon['statements'] = statements
	return mon


def get_repository_db_id(monitor, repo_properties):
	endpoint = repo_properties['endpoint']

	# setup the database connection
	engine = monitor['engine']
	conn = engine.connect()

	# lookup the repository record
	statement = monitor['statements']['repository_select']
	res = conn.execute(statement, endpoint=endpoint)

	if res.rowcount == 1:
		row = res.fetchone()
		repo_id =  row['id']
	elif res.rowcount > 1:
		# something has gone terribly wrong
		_logger.error("duplicate rows in repository table for endpoint %s", endpoint)
		raise Exception("duplicate rows in repository table for endpoint %s" % (endpoint))
	else:
		statement = monitor['statements']['repository_insert']
		res = conn.execute(statement, id=None, endpoint=repo_properties['endpoint'])
		repo_id = res.inserted_primary_key
	conn.close()
	return repo_id


def get_active_discos(monitor, record_id, endpoint):
	statement = monitor['statements']['active_discos']
	conn = monitor['engine'].connect()
	res = conn.execute(statement, endpoint=endpoint, record_id=record_id)
	discos = [ row['disco_id'] for row in res.fetchall() ]
	return discos

def monitor(monitor, record_id, active, repo_properties, rmap_properties):
	# get the repository table id for the endpoint (create record, if necessary)
	# add or update the monitor status record. if update, need to handle deletion of active record
	# add an active or deleted entry to the appropriate table (active or deleted)
	repo_id = get_repository_db_id(monitor, repo_properties)
	# add or update the monitor status record
		# setup the database connection
	engine = monitor['engine']
	conn = engine.connect()

	endpoint = repo_properties['endpoint']
	disco_id = rmap_properties['disco_id']
	event_id = rmap_properties['event_id']

	# check for existing monitor entry
	statement = monitor['statements']['monitor_select']
	res = conn.execute(statement, repo_id=repo_id, record_id=record_id)

	if res.rowcount == 1:
		# existing monitor entry, so get it's id and update its status
		row = res.fetchone()
		monitor_id =  row['id']
		if active != row['active']:
			# we need to update the record
			statement = monitor['statements']['monitor_update']
			conn.execute(statement, monitor_id=monitor_id, active=active)
	elif res.rowcount > 1:
		# something has gone terribly wrong
		_logger.error("duplicate rows in monitor table for record id %s endpoint %s", record_id, endpoint)
		raise Exception("duplicate rows in monitor table for record id %s endpoint %s" % (record_id, endpoint))
	else:
		# no existing record, so make a new one
		statement = monitor['statements']['monitor_insert']
		res = conn.execute(statement, id=None, record_id=record_id, repo_id=repo_id, active=active)
		monitor_id = res.inserted_primary_key

	if active:
		statement = monitor['statements']['creation_insert']
		res = conn.execute(statement, monitor_id=monitor_id, disco_id=disco_id, event_id=event_id,
		                   event_date=datetime.datetime.utcnow())
	else:
		statement = monitor['statements']['deletion_insert']
		res = conn.execute(statement, monitor_id=monitor_id, disco_id=disco_id, event_id=event_id,
		                   event_date=datetime.datetime.utcnow())
	conn.close()


def monitor_deleted(record_id, ):
	# get repository id or create new repository entry (id (key), endpoint)
	# lookup monitor entry (id + record_id) status
	# if deleted
	# - something is wrong, since there should not be more than one deletion
	# if active
	# - get disco_id
	# - inactivate disco
	# - update monitor entry with new status (active=False)
	# - update deletion table with event_id and time
	# Otherwise, this is a record_id that we've never seen before
	# - insert new monitor entry with active=False
	pass


def monitor_active():
	# get repository id or create new repository entry (id (key), endpoint)
	# lookup monitor entry
	# if active, then this is an update of an active record
	# - get disco_id
	# - update disco
	# else, this is a new active record
	# - insert new entry into monitor table
	# - insert new entry into creation table
	pass


def wipe_db(config):
	db_type = config['class']
	hostname = config['hostname']
	encoding = config['encoding']

	# get user credentials
	monitor_db = config['database']
	monitor_user = config['auth']['username']
	monitor_pass = config['auth']['password']

	# get database manager credentials
	dba_db = config['dba_auth']['database']
	dba_user = config['dba_auth']['username']
	dba_pass = config['dba_auth']['password']

	# create rmap user and db
	engine = _get_db_engine(db_type, dba_db, hostname, dba_user, dba_pass, encoding=encoding)

	conn = engine.connect()
	conn.execute("commit")

	try:
		conn.execute("drop database " + monitor_db)
	except OperationalError:
		# Expect this to fail, if DB doesn't already exist
		pass
	conn.execute("create database " + monitor_db)
	conn.execute("use " + monitor_db)
	try:
		conn.execute("create user '" + monitor_user + "'@'" + hostname + "' identified by '" + monitor_pass + "'")
	except OperationalError:
		# Expect this to fail, if user already exists
		pass
	#
	conn.execute(
		"grant insert, select, update, delete on " + monitor_db + ".* to '" + monitor_user + "'@'" + hostname + "'")

	# reconnect as DBA to the new database
	engine = _get_db_engine(db_type, monitor_db, hostname, dba_user, dba_pass, encoding=encoding)
	conn = engine.connect()
	conn.execute("commit")

	# create the necessary tables and indexes
	metadata = get_db_metadata()
	metadata.create_all(engine)

#######################################################################
# main()
#######################################################################
if __name__ == "__main__":
	import uuid
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument('--initializedb', dest='initialize_db', default=False, action='store_true',
	                    help='initialize the database (WARNING: will discard ALL data')
	parser.add_argument('-t', '--test', dest='test', default=False, action='store_true',
	                    help='run in test mode')
	parser.add_argument('-c', '--config', dest='config', default=DEFAULT_CONFIG_FILE,
	                    help='main configuration file')
	parser.add_argument('--credentials', dest='credentials', default=DEFAULT_CREDENTIALS_FILE,
	                    help='credentials configuration file')
	parser.add_argument('--mgrkey', dest='mgr_key', default=DEFAULT_MGR_AUTH_KEY,
	                    help='key for SQL manager credentials in credentials configuration file')
	args = parser.parse_args()

	mon_cfg = config.Config(filename=args.config, key="monitor_db")

	if args.initialize_db:
		mon_cfg['dba_auth'] = config._get_config_dict_from_file('monitor_dba.cfg', key='monitor_dba_auth')
		wipe_db(mon_cfg)

	if args.test:
		m = get_monitor_from_config(mon_cfg)
		monitor(m, 'oai:oai.datacite.org:'+str(uuid.uuid4()), True,
		        {'endpoint':'http://oai.datacite.org/oai/test',},
		        {'disco_id':'noah://disco.'+str(uuid.uuid4()), 'event_id':'noah://event'+str(uuid.uuid4())}
		        )


#######################################################################
# Epilogue
#######################################################################
_logger.debug("Module '%s' loaded", __name__)
