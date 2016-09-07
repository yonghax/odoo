# -*- coding: utf-8 -*-
import openerp.addons.decimal_precision as dp

from openerp import models, fields, api, _
from ...unit.backend_adapter import GenericAdapter

class account_invoice(models.Model):
    _inherit = 'account.invoice'

    payment_method = fields.Char(
        string='Payment Method',
    )

class sale_order(models.Model):
    _inherit = 'sale.order'
    
    payment_method = fields.Char(
        string='Payment Method',
    )
    
    prestashop_bind_ids = fields.One2many(
            comodel_name='prestashop.sale.order', 
            inverse_name='openerp_id',            
            string="Prestashop Bindings"
        )
    
    prestashop_order_id = fields.Integer(
                    related="prestashop_bind_ids.prestashop_id", 
                    store=True, 
                    string="Order_id On prestashop",
                    default=False,
                    index=True)
    
    prestashop_invoice_number = fields.Char(
                    related="prestashop_bind_ids.prestashop_invoice_number",
                    store=False,
                    string="Invoice Number",
                    )
    
    @api.multi
    def action_invoice_create(self, date_invoice, grouped=False, final=False):
        """In order to follow the invoice number of prestashop, 
        all the invoices generated from this workflow have to be tagged 
        with the prestashop_invoice_number
        In case of the invoice is not generated mainly from PS (eg : workflow accept invoice unpaid)
        the prestashop_invoice_number will be empty and won't cause troubles, 
        the usual invoice number associated to the journal will be used.
        """
        res = super(sale_order,self).action_invoice_create(grouped=grouped, final=final)
        
            
        #it can't be a grouped invoice creation so deal with that
        inv_ids = self.env['account.invoice'].browse(res)
        new_name = self.name
        if self.prestashop_order_id and self.prestashop_order_id > 0 :
            new_name = `self.prestashop_order_id` + '-'+  new_name                    

        inv_ids.write({
            'internal_number' :self.prestashop_invoice_number,
            'origin' : new_name,
        })
        
        if len(self.prestashop_bind_ids) == 1 and self.prestashop_bind_ids[0].backend_id.journal_id.id :
            #we also have to set the journal for the invoicing only for 
            #orders coming from the connector
            inv_ids.write({
                'journal_id': self.prestashop_bind_ids[0].backend_id.journal_id.id,
                'payment_method': self.payment_method,
                'date_invoice': date_invoice, 
                'state': 'open'
            })
            
        return res
    
    @api.model
    def _prepare_procurement_group(self):   
        #Improve the origin of shipping and name of the procurement group for better tracability
        new_name = self.name 
        if self.prestashop_order_id > 0 :
            new_name = `self.prestashop_order_id` + '-' + new_name        
        return {'name': new_name , 'partner_id': self.partner_shipping_id.id}
    
    @api.multi
    def _prepare_order_line_procurement(self):
        #Improve the origin of shipping and name of the procurement group for better tracability
        new_name = self.name
        if self.prestashop_order_id > 0 :
            new_name = `self.prestashop_order_id` + '-'+  new_name
        vals = super(sale_order, self)._prepare_order_line_procurement(group_id=group_id)        
        vals['origin'] = new_name
        return vals

class prestashop_sale_order(models.Model):
    _name = 'prestashop.sale.order'
    _inherit = 'prestashop.binding'
    _inherits = {'sale.order': 'openerp_id'}

   
    openerp_id = fields.Many2one(
            comodel_name = 'sale.order',
            string='Sale Order',
            required=True,
            ondelete='cascade'
            )
    prestashop_order_line_ids = fields.One2many(
            comodel_name = 'prestashop.sale.order.line',
            inverse_name = 'prestashop_order_id',
            string = 'Prestashop Order Lines'
        )
    prestashop_discount_line_ids = fields.One2many(
            comodel_name = 'prestashop.sale.order.line.discount',
            inverse_name = 'prestashop_order_id',
            string = 'Prestashop Discount Lines'
            )
    prestashop_invoice_number = fields.Char(
            string = 'PrestaShop Invoice Number', size=64
            )
    prestashop_delivery_number = fields.Char(
            string = 'PrestaShop Delivery Number', size=64
        )
    total_amount = fields.Float(
            string = 'Total amount in Prestashop',
            digits_compute=dp.get_precision('Account'),
            readonly=True
        )
    total_amount_tax = fields.Float(
            string = 'Total tax in Prestashop',
            digits_compute=dp.get_precision('Account'),
            readonly=True
        )
    total_shipping_tax_included = fields.Float(
            string = 'Total shipping in Prestashop',
            digits_compute=dp.get_precision('Account'),
            readonly=True
        )
    total_shipping_tax_excluded = fields.Float(
            string = 'Total shipping in Prestashop',
            digits_compute=dp.get_precision('Account'),
            readonly=True
        )
    payment = fields.Char(
        string='Payment Method',
    )
    
    @api.model
    def create_payments(self, ps_orders):
        _logger.debug("CREATE PAYMENTS")
        _logger.debug(ps_orders)
        
        for order in self.browse(ps_orders ):
            _logger.debug("CHECK for order %s with id %s" % (order.name, order.openerp_id.id))     
                                           
            session = ConnectorSession(self.env.cr, self.env.uid,
                                   context=self.env.context)
            backend_id = order.backend_id
            env = get_environment(session, 'prestashop.sale.order', backend_id.id)
            _logger.debug(env)
            
            adapter = env.get_connector_unit(SaleOrderAdapter)
            ps_order = adapter.read(order.prestashop_id)
            #Force the rules check
            rules = env.get_connector_unit(SaleImportRule)
            rules.check(ps_order)
            
            if rules._get_paid_amount(ps_order) and \
                    rules._get_paid_amount(ps_order) >= 0.0 :
                amount = float(rules._get_paid_amount(ps_order))
                order.openerp_id.automatic_payment(amount)
            
class sale_order_line(models.Model):
    _inherit = 'sale.order.line'
   
    prestashop_bind_ids = fields.One2many(
            comodel_name = 'prestashop.sale.order.line',
            inverse_name = 'openerp_id',
            string="PrestaShop Bindings"
        )
    prestashop_discount_bind_ids = fields.One2many(
            comodel_name = 'prestashop.sale.order.line.discount',
            inverse_name = 'openerp_id',
            string="PrestaShop Discount Bindings"
        )
    

class prestashop_sale_order_line(models.Model):
    _name = 'prestashop.sale.order.line'
    _inherit = 'prestashop.binding'
    _inherits = {'sale.order.line': 'openerp_id'}

    openerp_id = fields.Many2one(
            comodel_name = 'sale.order.line',
            string='Sale Order line',
            required=True,
            ondelete='cascade'
        )
    prestashop_order_id = fields.Many2one(
            comodel_name = 'prestashop.sale.order',
            string = 'Prestashop Sale Order',
            required=True,
            ondelete='cascade',
            select=True
        )
    

    @api.v7
    def create(self, cr, uid, vals, context=None):
        prestashop_order_id = vals['prestashop_order_id']
        info = self.pool['prestashop.sale.order'].read(
            cr, uid,
            [prestashop_order_id],
            ['openerp_id'],
            context=context
        )
        order_id = info[0]['openerp_id']
        vals['order_id'] = order_id[0]
        return super(prestashop_sale_order_line, self).create(
            cr, uid, vals, context=context
        )


class prestashop_sale_order_line_discount(models.Model):
    _name = 'prestashop.sale.order.line.discount'
    _inherit = 'prestashop.binding'
    _inherits = {'sale.order.line': 'openerp_id'}

    openerp_id = fields.Many2one(
            comodel_name = 'sale.order.line',
            string='Sale Order line',
            required=True,
            ondelete='cascade'
        )
    prestashop_order_id = fields.Many2one(
            comodel_name = 'prestashop.sale.order',
            string = 'Prestashop Sale Order',
            required=True,
            ondelete='cascade',
            select=True
        )
    
    @api.v7
    def create(self, cr, uid, vals, context=None):
        prestashop_order_id = vals['prestashop_order_id']
        info = self.pool['prestashop.sale.order'].read(
            cr, uid,
            [prestashop_order_id],
            ['openerp_id'],
            context=context
        )
        order_id = info[0]['openerp_id']        
        vals['order_id'] = order_id[0]
        return super(prestashop_sale_order_line_discount, self).create(
            cr, uid, vals, context=context
        )
