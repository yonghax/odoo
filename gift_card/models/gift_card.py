# -*- coding: utf-8 -*-

from openerp import models, fields, api, _

import logging
_logger = logging.getLogger(__name__)

class gift_card(models.Model):
	_name = 'gift.card'

	code = fields.Char( string='Code', required=True, )
	name = fields.Char( string='Name' )
	date_start = fields.Date( string='Start Date' )
	date_end = fields.Date( 
		string='End Date',
		default=fields.Date.today
	)
	type = fields.Selection(
		string = 'Type',
		selection = ([('amount', 'Amount'),('percent', 'Percent')])
	)

	amount = fields.Float( string='Amount' )
	residual_amount = fields.Float( string='Residual Amount' )
	used = fields.Boolean( string='Used' )

	data_type = fields.Selection(
		string = 'Data Type',
		selection = ([('import', 'Import'),('manual', 'Manual')])
	)

	_sql_constraints = [
	    ('code_uniques', 'unique (code)', ('The code must be unique !')),
	]

	@api.onchange('amount')
	@api.one
	def _onchange_amount(self):
		if self.type == 'amount':
			self.residual_amount = self.amount
		else:
			self.residual_amount = 0

	@api.constraint('amount')
	@api.one
	def contraint_val(self):
		_logger.info('runnn contstrain amount')
		if self.type == 'percent':
			if self.amount > 100:
				raise("Amount can't greater than 100")
			elif self.amount < 0:
				raise("Amonut can't less than 0")

	@api.constraint('date_start')
	@api.one
	def date_val(self):
		if self.date_start > self.date_end:
			raise("Start Date can't be greater than End Date")