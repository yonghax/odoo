from datetime import date, datetime

from openerp import api, fields, models, _
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT

import openerp.addons.decimal_precision as dp

class switchover_product(models.Model):
    _name = 'switchover.product'
    _inherit = 'mail.thread'
    _order = 'create_date desc, date_expect asc'
    _description = "Switch-over Product"

    name = fields.Char('Reference', select=True, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, copy=False)
    location_id = fields.Many2one('stock.location', 'Location', required=True, ondelete='restrict', readonly=True, select=True, auto_join=True,states={'draft': [('readonly', False)]})
    date_expect = fields.Date(string='Expected Date',required=False,readonly=True,states={'draft': [('readonly', False)]})
    date_done = fields.Datetime(string='Date Validated',required=False,readonly=True,)
    state = fields.Selection([('draft', 'Draft'),('done', 'Done'),('cancel', 'Cancelled')], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    notes = fields.Text(string='Note',required=True,states={'draft': [('readonly', False)]},readonly=True,)
    swithcover_lines = fields.One2many('switchover.product.line', 'switchover_id', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    
    @api.multi
    def action_done(self):
        self.post_switchover()

    def post_switchover(self):
        """ Changes the Product Quantity by making a Physical Inventory. """
        context = self.env.context
        cr = self.env.cr
        uid = self.env.uid

        inventory_obj = self.pool.get('stock.inventory')

        ctx = context.copy()
        ctx['location'] = self.location_id.id
            
        inventory_id = inventory_obj.create(cr, uid, {
            'name': _('SWITCH INV: %s') % self.create_date,
            'filter': 'partial',
            'location_id': self.location_id.id,
            'is_switchover_stock': True
            }, context=context)

        for line in self.swithcover_lines:
            if line.product_qty < 0:
                raise UserError(_('Quantity cannot be negative.'))
            else:
                self.create_inventory_line(inventory_id, line, context=context)
        
        inventory_obj.action_done(cr, uid, [inventory_id], context=context)
        
        self.with_context(ctx).write(
        {
            'name': _('SWITCH INV: %s') % self.create_date,
            'date_done': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'state':'done',
        })

        return {}

    def create_inventory_line(self, inventory_id, line, context=None):

        res = {}
        cr = self.env.cr
        uid = self.env.uid
        inventory_line_obj = self.pool.get('stock.inventory.line')
        product = line.product_id.with_context(location=line.switchover_id.location_id.id)
        mapping_product = line.product_id.switchover_product_mapping.with_context(location=line.switchover_id.location_id.id)

        th_qty = product.qty_available
        th_qty_mapping = mapping_product.qty_available

        if th_qty_mapping < line.product_qty:
            raise UserError(_('Quantity not enough.'))

        qty_mapping = th_qty_mapping - line.product_qty
        qty_switchover = th_qty + line.product_qty

        res = {
            'inventory_id': inventory_id,
            'product_qty': qty_mapping,
            'location_id': line.switchover_id.location_id.id,
            'product_id': mapping_product.id,
            'product_uom_id': mapping_product.uom_id.id,
            'theoretical_qty': th_qty_mapping,
        }
        inventory_line_obj.create(cr, uid,res, context=context)

        res = {
            'inventory_id': inventory_id,
            'product_qty': qty_switchover,
            'location_id': line.switchover_id.location_id.id,
            'product_id': product.id,
            'product_uom_id': product.uom_id.id,
            'theoretical_qty': th_qty,
        }
        inventory_line_obj.create(cr, uid,res, context=context)

        return res

class switchover_product_line(models.Model):
    _name = 'switchover.product.line'

    switchover_id = fields.Many2one(string='Switch-over Product',comodel_name='switchover.product', ondelete='cascade')
    product_id = fields.Many2one(string='Switch-over Product',required=True,comodel_name='product.product',domain=[('is_product_switchover','=',True)],ondelete='restrict')
    product_uom_id= fields.Many2one('product.uom', 'Product Unit of Measure', required=True)
    product_qty = fields.Float(string='Quantity', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0)

    def product_id_change(self, cr, uid, ids, product_id, product_uom_id, product_qty, context=None):
        res = self.on_change_tests(cr, uid, ids, product_id, product_uom_id, product_qty, context=context)
        uom_obj = self.pool['product.uom']
        product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
        if product_id and not product_uom_id or uom_obj.browse(cr, uid, product_uom_id, context=context).category_id.id != product.uom_id.category_id.id:
            res['value']['product_uom_id'] = product.uom_id.id
        if product:
            res['value']['lots_visible'] = (product.tracking != 'none')
            res['domain'] = {'product_uom_id': [('category_id','=',product.uom_id.category_id.id)]}
        else:
            res['domain'] = {'product_uom_id': []}
        return res

    def on_change_tests(self, cr, uid, ids, product_id, product_uom_id, product_qty, context=None):
        res = {'value': {}}
        uom_obj = self.pool.get('product.uom')
        if product_id:
            product = self.pool.get('product.product').browse(cr, uid, product_id, context=context)
            product_uom_id = product_uom_id or product.uom_id.id
            selected_uom = uom_obj.browse(cr, uid, product_uom_id, context=context)
            if selected_uom.category_id.id != product.uom_id.category_id.id:
                res['warning'] = {
                    'title': _('Warning: wrong UoM!'),
                    'message': _('The selected UoM for product %s is not compatible with the UoM set on the product form. \nPlease choose an UoM within the same UoM category.') % (product.name)
                }
            if product_qty and 'warning' not in res:
                rounded_qty = uom_obj._compute_qty(cr, uid, product_uom_id, product_qty, product_uom_id, round=True)
                if rounded_qty != product_qty:
                    res['warning'] = {
                        'title': _('Warning: wrong quantity!'),
                        'message': _('The chosen quantity for product %s is not compatible with the UoM rounding. It will be automatically converted at confirmation') % (product.name)
                    }

            th_qty = product.switchover_product_mapping.qty_available
            if th_qty < product_qty:
                res['warning'] = {
                    'title': _('Warning: wrong quantity!'),
                    'message': _('The chosen quantity for product %s is not enough to switch. Available qty remaining %d') % (product.name, th_qty)
                }

        return res
        