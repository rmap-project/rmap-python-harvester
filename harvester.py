# -*- coding: utf-8 -*-
# coding: utf-8
# oai_pmh_harvest.py
__author__ = 'tim.dilauro@jhu.edu'
__version__ = '0.1.'


import sys
import copy
import traceback
import logging

import sickle
from sickle import Sickle
import sickle.app

from sickle.models import Identify

#######################################################################
# Classes
#######################################################################
class Harvester(Sickle):
	"""Client for harvesting OAI interfaces.

	Use it like this::

		>>> harvester = Harvester('http://elis.da.ulcc.ac.uk/cgi/oai2')
		>>> records = harvester.ListRecords(metadataPrefix='oai_dc')
		>>> records.next()
		<Record oai:eprints.rclis.org:3780>

	:param endpoint: The endpoint of the OAI interface.
	:type endpoint: str
	:param http_method: Method used for requests (GET or POST, default: GET).
	:type http_method: str
	:param protocol_version: The OAI protocol version.
	:type protocol_version: str
	:param max_retries: Number of retries if HTTP request fails.
	:type max_retries: int
	:param timeout: Timeout for HTTP requests.
	:type timeout: int
	:type protocol_version: str
	:param class_mapping: A dictionary that maps OAI verbs to classes representing
						  OAI items. If not provided,
						  :data:`sickle.app.DEFAULT_CLASS_MAPPING` will be used.
	:type class_mapping: dict
	:param auth: An optional tuple ('username', 'password')
				 for accessing protected OAI interfaces.
	:type auth: tuple
	:param nickname: A short name for the harvester
	:type nickname: str
	:param fullname: A longer name for the harvester
	:type fullname: str
	:param response_callback: A function that will be called for each HTTP response
	:type response_callback: callable
	"""
	def __init__(self, *a, **kw):
		self.args = a
		self.params = kw
		self.response_callback = kw.pop('response_callback', None)
		self.nickname = kw.pop('nickname', None)
		self.fullname = kw.pop('fullname', None)
		self.metadataPrefix = kw.pop('metadataPrefix', None)
		self.sickle_params = kw
		self.sickle_args = a
		# Initialize my superclass
		super(Harvester, self).__init__(*a, **kw)

	"""
	This method is sub-classed so that we can intercept the call to support callback functionality.
	"""
	def harvest(self, response_callback=None, **kw):
		response_callback = kw.pop('response_callback', self.response_callback)
		# call super class to do most of the work
		response = super(Harvester, self).harvest(**kw)
		if response_callback is not None and callable(self.response_callback):
			self.response_callback(response)
		return response

	"""
	def ListRecords(self, ignore_deleted=False, **kw):
		response = Sickle.ListRecords(self, ignore_deleted=ignore_deleted, **kw)
		return response
	"""

	def ListRecords(self, ignore_deleted=False, callback=None, **kwargs):
		"""Issue a ListRecords request.

		:param ignore_deleted: If set to :obj:`True`, the resulting
							  :class:`sickle.app.OAIIterator` will skip records
							  flagged as deleted.
		:rtype: :class:`harvester.OAIIterator`
		"""
		params = kwargs
		params.update({'verb': 'ListRecords'})
		# params.update({'callback': callback})
		# clone the Harvester, so that changes or deletions don't cause problems
		h = copy.deepcopy(self)
		h.last_response = h.harvest(**params)
		return OAIIterator(h.last_response, h, ignore_deleted=ignore_deleted, callback=callback)


	def Event_ListRecords(self, ignore_deleted=False, callback=None, **kwargs):
		if callback is not None and callable(callback):
			iterator = self.ListRecords(ignore_deleted=ignore_deleted, callback=callback, **kwargs)
		else:
			raise ValueError("callback must be callable")

		# iterate the records to invoke the callback
		for record in iterator: pass



class OAIIterator(sickle.app.OAIIterator):
	"""Iterator over OAI records/identifiers/sets transparently aggregated via
	OAI-PMH.

	Can be used to conveniently iterate through the records of a repository.

	:param oai_response: The first OAI response.
	:type oai_response: :class:`sickle.app.OAIResponse`
	:param sickle: The Sickle object that issued the first request.
	:type sickle: :class:`sickle.app.Sickle`
	:param ignore_deleted: Flag for whether to ignore deleted records.
	:type ignore_deleted: bool

	:param callback: A function that will be called for each HTTP response
	:type callback: callable
	"""
	def __init__(self, oai_response, harvester, ignore_deleted=False, callback=None):
		self.harvester = harvester
		self.callback = callback
		super(OAIIterator, self).__init__(oai_response, self.harvester, ignore_deleted)

	def _next_response(self):
		"""Get the next response from the OAI server."""
		# keep track of the active resumption token, in case we have to restart part way through
		self.last_resumption_token = self.resumption_token
		super(OAIIterator, self)._next_response()

	def next(self):
		result = super(OAIIterator, self).next()
		if self.callback is not None and callable(self.callback):
			self.callback(self, self.element, result)
		return result


#######################################################################
# End of Functions
#######################################################################

if __name__ == '__main__':
	# sys.stderr.write( "%s is a module and is not meant to be run directly.", __file__)
	# sys.stderr.flush()

	def response_handler(response):
		print "**\n** Entering response_handler()\n**\n"

	def record_handler(obj, element, value):
		print "harvester.py:record_handler: element: %s; id: %s; rt=[%s]" % \
			  (element, value.header.identifier, obj.resumption_token if obj.resumption_token is not None else '')

	h = Harvester('http://oai.datacite.org/oai', response_callback=response_handler)
	i = h.Identify()
	"""
	for record in h.Event_ListRecords(metadataPrefix='oai_datacite', callback=record_handler):
		print("harvester.py:__main__: record id=%s" % (record.header.identifier) )
	"""
	for record in h.Event_ListRecords(resumptionToken='1431465368648,0001-01-01T00:00:00Z,9999-12-31T23:59:59Z,200,null,oai_datacite', callback=record_handler):
		print("harvester.py:__main__: record id=%s" % (record.header.identifier) )