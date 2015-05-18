__author__ = 'timmo'

import httplib
from urlparse import urlparse
import base64
import logging

"""
Normalize some invalid characters out of eXist-db object paths
TODO: Other characters that shouldn't make it into the eXist-db path?
"""
def normalize_path(path):
	if path is not None:
		path = path.replace(':', '/')
	return path


"""
consider using "requests" module
- https://pypi.python.org/pypi/requests

from existdb import ExistDB
edb = ExistDB('http://localhost:8080/exist/rest')
edb.authenticate('admin','')
edb.set_collection('rmap-datacite')
edb.store('<record2/>', 'test1.xml')
edb.store('<x>Here is some test text </x>', 'testx.xml')
"""
class ExistDB:
	def __init__(self, endpoint):
		o = urlparse(endpoint)
		self.__location = o.netloc
		self.__api_path =  o.path
		#self.__con = httplib.HTTP(self.__location)

	def set_collection(self, collection):
		self.__collection = collection

	def authenticate(self, username, password):
		# base64 encode the username and password
		self.__auth = base64.encodestring('%s:%s' % (username, password)).replace('\n', '')

	def logout(self):
		self.__auth = None

	def store(self, document, name, collection=None):
		if collection is None:
			collection = self.__collection

		# unicode or ascii text needs to be encoded in order to be sent
		document = document.encode('utf-8')

		#print "storing document to collection %s/%s ..." % (collection, name)
		try:
			con = httplib.HTTP(self.__location)
			con.putrequest('PUT', self.__api_path + normalize_path('/%s/%s' % (collection, name)))
			con.putheader('Content-Type', 'application/xml; charset=utf-8')
			con.putheader("Content-length", "%d" % len(document))
			if self.__auth is not None:
				con.putheader("Authorization", "Basic %s" % self.__auth)
			con.endheaders()
			con.send(document)
			errcode, errmsg, headers = con.getreply()
			f = con.getfile()
			# f.close() - in finally
			if errcode != 201:
				logging.error('An error occurred: %s', errmsg)
			else:
				logging.info('Success: %s', errmsg)
		finally:
			con.close()
			f.close()
		return errcode, errmsg, headers

	def retrieve(self, doc, collection=None):
		"""
		this method is not complete
		"""
		try:
			if collection is None:
				collection = self.__collection
			con = httplib.HTTP(self.__location)
			con.putrequest('GET', self.__api_path + '/%s/%s' % (collection, doc))
			con.putheader("Authorization", "Basic %s" % self.__auth)
			errcode, errmsg, headers = con.getreply()
			f = con.getfile()
		finally:
			con.close()
			f.close()
		return doc


