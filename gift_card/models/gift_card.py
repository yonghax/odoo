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
			proses_import_data_ps.delay(session,'gift.card', x['id_cart_rule'],priority=10)

	def _prepare_move_line(self, move, invoice, debit_account_id, credit_account_id):
		debit_amount = self.amount
		credit_amount = invoice.residual if self.amount >= invoice.residual else self.amount 
		balance_amount = debit_amount - credit_amount
		other_income_account = self.env.ref('account.other_income_account')
		vals = []

		debit_line_vals = {
			'ref': self.code,
			'name': 'Gift Card Used: %s' % (self.code),
			'debit': debit_amount,
			'credit': 0,
			'account_id': debit_account_id.id,
        }

		vals.append((0, 0, debit_line_vals))

		credit_line_vals = {
			'ref': '%s - %s' % (invoice.origin, self.code),
			'name': 'Payment %s Used Gift Card %s' % (invoice.origin, self.code),
			'partner_id': invoice.partner_id.id,
			'debit': 0,
			'credit': credit_amount,
			'account_id': credit_account_id.id,
        }
		vals.append((0, 0, credit_line_vals))
		
		if balance_amount != 0:
			credit_line_vals = {
				'ref': self.code,
				'name': 'Income From Gift Card %s' % (self.code),
				'partner_id': invoice.partner_id.id,
				'debit': 0,
				'credit': balance_amount,
				'account_id': other_income_account.id,
			}
			vals.append((0, 0, credit_line_vals))
		return vals
			
	def create_reclass_journal(self, invoice):
		move_obj = self.env['account.move']
		journal_id = self.env.ref('account.account_journal_voucher')
		unearned_account = self.env.ref('account.unearned_revenue_account')
		account_id = invoice.account_id
		account_reconcilleds = []
		if not unearned_account:
			unearned_account = self.env['account.account'].search([('code', '=', '2.01000-10')])
		
		move_lines = self._prepare_move_line(move_obj, invoice, unearned_account, account_id)
		new_move = move_obj.create({
			'journal_id': journal_id.id,
			'line_ids': move_lines,
			'date': invoice.date_invoice,
			'ref': invoice.origin})
		new_move.post()
		self.recon_sales(invoice, new_move)

	def recon_sales(self, invoice, account_move):
		move_line_obj = self.env['account.move.line']
		account_reconcilleds = []
		
		account_reconcilleds.append(account_move.line_ids.filtered(lambda x: x.account_id.internal_type in ['payable','receivable']))
		account_reconcilleds.append(invoice.move_id.line_ids.filtered(lambda x: x.account_id.internal_type in ['payable','receivable']))

		debit = sum([x['debit'] for x in account_reconcilleds])
		credit = sum([x['credit'] for x in account_reconcilleds])
		balance = debit - credit

		if balance == 0:
			wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in account_reconcilleds]).create({})
			wizard.trans_rec_reconcile_full()
			invoice.confirm_paid()
			assert invoice.state == 'paid', "Invoice not paid"
		else:
			wizard = self.env['account.move.line.reconcile'].with_context(active_ids=[x.id for x in account_reconcilleds]).create({})
			wizard.trans_rec_reconcile_partial_reconcile()

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
			gift_card = gift_card_obj.search([('prestashop_id', '=', prestashop_id)])
			if gift_card:
				print 'gift card write!'
				gift_card.write(data)
				gift_card.refresh()
				return gift_card
			else:
				return gift_card_obj.create(data)

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
		
		pres_back.write({'import_gift_card_since':datetime.now()})
		cur.execute(query)
		result = cur.fetchall()
		
		cur.close()
		db.close()

		return result