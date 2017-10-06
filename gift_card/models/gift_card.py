# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
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
		selection = ([('amount', 'Amount'),('percent', 'Percent')]),
		default = 'amount'
	)

	amount = fields.Float( string='Amount' )
	residual_amount = fields.Float( string='Residual Amount' )
	used = fields.Boolean( string='Used' )

	data_type = fields.Selection(
		string = 'Data Type',
		selection = ([('import', 'Import'),('manual', 'Manual')])
	)

	prestashop_id = fields.Integer(
		string='Preshtashop ID'
	)
	
	is_voucher = fields.Boolean(
		string='Is Voucher',
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

	@api.constrains('amount')
	@api.one
	def contraint_val(self):
		_logger.info('runnn contstrain amount')
		if self.type == 'percent':
			if self.amount > 100:
				raise ValidationError("Amount can't greater than 100")
			elif self.amount < 0:
				raise ValidationError("Amonut can't less than 0")

	@api.constrains('date_start')
	@api.one
	def date_val(self):
		if self.date_start > self.date_end:
			raise ValidationError("Start Date can't be greater than End Date")


