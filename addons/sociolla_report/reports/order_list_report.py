from openerp import api, fields, models, _
import openerp.addons.decimal_precision as dp


class list_report(models.TransientModel):
    _name = 'list.report'
    date_from = fields.Date(string=u'Start Date',)
    date_to = fields.Date(string=u'Start Date',)
    
    order_ids = fields.One2many(
        string=u'List Order',
        comodel_name='order.list.report',
        inverse_name='list_id',
    )


class order_list_report(models.TransientModel):
    _name = 'order.list.report'

    list_id = fields.Many2one(
        string='',
        comodel_name='list.report'
    )

    type = fields.Selection(
        string=u'Type',
        default='purchase',
        selection=[('purchase', 'Purchase Order'), ('sales', 'Sales Order')]
    )
    order_reference = fields.Char(
        string=u'Order Reference',
    )
    order_date = fields.Datetime(
        string=u'Order Date',
        default=fields.Datetime.now,
    )
    order_status = fields.Char(
        string=u'Status',
    )
    partner_id = fields.Many2one(
        string=u'Partner',
        comodel_name='res.partner',
        ondelete='set null',
    )
    picking_status = fields.Char(
        string=u'Picking Status',
    )
    invoice_status = fields.Char(
        string=u'Invoicing Status',
    )
    currency_id = fields.Many2one(
        string=u'Currency',
        comodel_name='res.currency',
    )
    notes = fields.Text(string=u'Notes',)
    untaxed_amount = fields.Monetary(string=u'Untaxed Amount', default=0.0)
    tax_amount = fields.Monetary(string=u'Tax Amount', default=0.0)
    total_amount = fields.Monetary(string=u'Total Amount', default=0.0)

class order_list_report_line(models.TransientModel):
    _name = 'order.list.report.line'

    order_list_id = fields.Many2one(
        string=u'Parent',
        comodel_name='order.list.report',
    )
    product_id = fields.Many2one(
        string=u'Product',
        comodel_name='product.product',
    )
    product_reference = fields.Char(string=u'Product Reference',)
    name = fields.Char(string=u'Description',)
    quantity = fields.Integer(string=u'Quantity',)
    price_unit = fields.Float('Unit Price', required=True, digits=dp.get_precision('Product Price'), default=0.0)
    qty_picking =  fields.Integer(string=u'Quantity Picking',)
    qty_invoiced =  fields.Integer(string=u'Quantity Invoiced',)
    currency_id = fields.Many2one(string=u'Currency',comodel_name='res.currency',)
    untaxed_amount = fields.Monetary(string=u'Untaxed Amount', default=0.0)
    tax_amount = fields.Monetary(string=u'Tax Amount', default=0.0)
    total_amount = fields.Monetary(string=u'Total Amount', default=0.0)
    discount = fields.Float('Discount', required=True, digits=dp.get_precision('Discount'), default=0.0)