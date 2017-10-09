
import pytz
from datetime import datetime
from itertools import groupby

from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp import api, fields, models, _

class payment(models.Model):
    
    _inherit = ['account.payment']
    
    sale_consignment_id = fields.Many2one(
        string=u'Reconcile Sale Consignment',
        comodel_name='reconcile.sale.consignment',
        ondelete='cascade',
    )

class account_move(models.Model):
    
    _inherit = ['account.move']
    sale_consignment_id = fields.Many2one(
        string=u'Reconcile Sale Consignment',
        comodel_name='reconcile.sale.consignment',
        ondelete='cascade',
    )
    
class reconcile_sale_consignment(models.Model):
    _name = 'reconcile.sale.consignment'
    
    name = fields.Char(
        string=u'Reference',
    )
    state = fields.Selection([('draft', 'Draft'),('posted', 'Posted')], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')    
    
    date_range_id = fields.Many2one(
        comodel_name='date.range',
        required=True,
        string='Date range', 
        readonly=True,
        ondelete='cascade'
    )
    start_date = fields.Date(
        string=u'Start Date', 
        readonly=True,
    )
    end_date = fields.Date(
        string=u'End Date',
        readonly=True,
    )
    partner_id = fields.Many2one(
        string=u'Vendor',
        comodel_name='res.partner',
        domain="[('supplier','=',True)]",
        readonly=True,
        ondelete='cascade'
    )
    currency_id = fields.Many2one(
        string=u'Currency ID',
        comodel_name='account.currency',
        ondelete='set null',
    )
    
    payment_date = fields.Date(
        string=u'Payment Date',
        states={'posted': [('readonly', True)]}
    )
    journal_id = fields.Many2one(
        string=u'Payment Method',
        comodel_name='account.journal',
        domain="[('at_least_one_outbound','=',True), ('type', 'in', ['bank', 'cash'])]",
        ondelete='cascade',
        auto_join=True,
        states={'posted': [('readonly', True)]}
    )
    payment_amount = fields.Float(
        string=u'Payment Amount',
        states={'posted': [('readonly', True)]}
    )
    memo = fields.Char(
        string=u'Memo',
        states={'posted': [('readonly', True)]}
    )
    amount_total = fields.Float(
        string=u'Total Amount',
    )
    amount_due = fields.Float(
        string=u'Amount Due',
    )
    adjust_type = fields.Selection(
        string=u'Debit / Credit',
        selection=[('debit', 'Debit'), ('credit', 'Credit')]
    )
    adjust_amount = fields.Float(
        string=u'Adjust Amount',
    )
    adjust_account = fields.Many2one(
        string=u'Adjust Account',
        comodel_name='account.account',
        ondelete='cascade',
    )
    adjust_memo = fields.Char(
        string=u'Adjust Memo',
    )
    
    payment_ids = fields.One2many(
        string=u'Payment',
        comodel_name='account.payment',
        inverse_name='sale_consignment_id',
        states={'posted': [('readonly', True)]}
    )
    line_ids = fields.One2many(
        string=u'Detail Lines',
        comodel_name='reconcile.sale.consignment.line',
        inverse_name='sale_consignment_id',
        states={'posted': [('readonly', True)]}
    )
    move_ids = fields.One2many(
        string=u'Account Move',
        comodel_name='account.move',
        inverse_name='sale_consignment_id',
        states={'posted': [('readonly', True)]}
    )
    
    @api.one
    def _prepare_account_payment(self):
        val = {}
        if self.state == 'posted':
            val = {
                'payment_type': 'outbound',
                'partner_type': 'supplier',
                'payment_method_id': self.env['account.payment.method'].search([('payment_type', '=', 'outbound')])[0],
                'partner_id': self.partner_id.id,
                'journal_id': self.journal_id,
                'payment_date': self.payment_date,
                'amount': self.payment_amount,
                'communication': self.memo,
                'currency_id': self.currency_id,
                'company_id': self.env.company_id.id,
                'state': 'draft',
            }

        return val

    @api.one
    @api.multi
    def post_reconcile(self):
        pass

    @api.one
    @api.multi
    def unpost_reconsile(self):
        if self.status == 'posted':
            payment_ids = self.payment_ids.ids
            move_ids = self.move_ids

    @api.multi
    def action_post(self):
        self.post_reconcile()

    @api.multi
    def action_cancel(self):
        self.unpost_reconsile()
    
class reconcile_sale_consignment_line(models.Model):
    _name = 'reconcile.sale.consignment.line'

    sale_consignment_id = fields.Many2one(
        string=u'Reconcile Sale Consignment',
        comodel_name='reconcile.sale.consignment',
    )
    product_brand_id = fields.Many2one(
        string=u'Product Brand',
        comodel_name='product.brand',
        readonly=True,
        ondelete='cascade',
    )
    product_id = fields.Many2one(
        string=u'Product',
        comodel_name='product.product',
        ondelete='cascade',
        readonly=True,
    )
    qty_sold = fields.Integer(
        string=u'Qty Sold',
        readonly=True,
    )
    cogs = fields.Float(
        string=u'Cost Value',
        readonly=True,
    )
    total = fields.Float(
        string=u'Total',
        readonly=True,
    )