# -*- coding: utf-8 -*-

from openerp import models, fields, api, _
from openerp.exceptions import ValidationError
from openerp.addons.connector.session import ConnectorSession
from openerp.addons.connector.queue.job import job
from datetime import datetime

import logging
_logger = logging.getLogger(__name__)

@job(default_channel='root')
def proses_import_data_ps(session, model_name, prestashop_id):
	obj = session.env['gift.card']
	obj.import_data_ps(prestashop_id)

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
	used = fields.Boolean( string='Used', default=False )
	data_type = fields.Selection(
		string = 'Data Type',
		selection = ([('import', 'Import'),('manual', 'Manual')]),
		default = 'manual'
	)
	prestashop_id = fields.Integer(
		string='Preshtashop ID'
	)
	is_voucher = fields.Boolean(
		string='Is Voucher',
		default = False
	)
	order_ids = fields.One2many(
		string=u'Order used',
		comodel_name='sale.order',
		inverse_name='gift_card_id',
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


	@api.model
	def _scheduler_import_data(self):
		session = ConnectorSession(self._cr, self._uid, context=self._context)
		for x in self.go_query_import_data_ps():
			proses_import_data_ps.delay(session,'gift.card', x['id_cart_rule'],priority=1)

		self.env['prestashop.backend'].browse(1).write({'import_gift_card_since':datetime.now()})

	def import_data_ps(self, prestashop_id):
		prestashop_cart_rule = self.go_query_import_data_ps(prestashop_id)

		gift_card_obj = self.env['gift.card']
		data = {}
		for x in prestashop_cart_rule:
			listing = dict(
				code=x['code'],
				name=x['description'],
				date_start = x['date_from'],
				date_end = x['date_to'],
				type = 'amount' if x['reduction_amount'] > 0 else 'percent',
				amount = x['reduction_amount'] if x['reduction_amount'] > 0 else x['reduction_percent'],
				residual_amount = x['reduction_amount'] if x['reduction_amount'] > 0 else x['reduction_percent'],
				data_type = 'import',
				used = False,
				is_voucher = False if x['sociolla_giftcard'] == 1 else True,
				prestashop_id = prestashop_id
			)
			data.update(listing)

			# create db
			gift_card_obj.create(data)

	def go_query_import_data_ps(self, id=None):
		import MySQLdb

		host = self.env['ir.config_parameter'].get_param('mysql.host')
		user = self.env['ir.config_parameter'].get_param('mysql.user')
		passwd = self.env['ir.config_parameter'].get_param('mysql.passwd')
		dbname = self.env['ir.config_parameter'].get_param('mysql.dbname')

		db = MySQLdb.connect(host, user, passwd, dbname, cursorclass=MySQLdb.cursors.DictCursor)
		cur = db.cursor()

		pres_back = self.env['prestashop.backend'].browse(1)
		if id:
			add_query = 'AND id_cart_rule = %s '%(id)
		else:
			add_query = "AND date_upd >= '%s' "%(pres_back.import_gift_card_since)

		query = '''
			SELECT id_cart_rule, code, description, date_from, date_to,
				reduction_amount, reduction_percent, sociolla_giftcard
			FROM ps_cart_rule
				WHERE active = 1 %s
		'''%(add_query)

		cur.execute(query)
		result = cur.fetchall()
		
		cur.close()
		db.close()

		return result






