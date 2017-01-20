from openerp import api, fields, models, _
from openerp.exceptions import UserError
import openerp.addons.decimal_precision as dp

class switchover_product(models.Model):
    _name = 'switchover.product'
    _inherit = ['mail.thread']
    _order = 'create_date desc, date_expect asc'

    name = fields.Char('Reference', select=True, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, copy=False)
    location_id = fields.Many2one('stock.location', 'Location', required=True, ondelete='restrict', readonly=True, select=True, auto_join=True,states={'draft': [('readonly', False)]})
    date_expect = fields.Datetime(
        string='Expected Date',
        required=False,
        readonly=True,
        default=fields.datetime.now
    )
    date_done = fields.Datetime(
        string='Date Validated',
        required=False,
        readonly=True,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
        ], string='Status', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')
    
    swithcover_lines = fields.One2many('switchover.product.line', 'switchover_id', states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, domain=[('product_id', '!=', False)])
    notes = fields.Text(string='Note',required=True,states={'draft': [('readonly', False)]},readonly=True,)
    
    def action_done(self):
        if self.qty <= 0:
            raise UserError(_('Quantity cannot must be greather then 0'))
        
        self.post_switchover()

    def post_switchover(self):
        if context is None:
            context = {}

        inventory_obj = self.pool.get('stock.inventory')
        inventory_line_obj = self.pool.get('stock.inventory.line')

        ctx = context.copy()
        ctx['location'] = self.location_id.id
        if self.product_id.id and self.lot_id.id:
            filter = 'none'
        elif self.product_id.id:
            filter = 'partial'
        else:
            filter = 'none'
        inventory_id = inventory_obj.create(cr, uid, {
            'name': _('SWITCH INV: %s') % tools.ustr(self.product_id.name),
            'filter': filter,
            'product_id': self.product_id.id,
            'location_id': self.location_id.id,
            'lot_id': self.lot_id.id}, context=context)

        line_self = self._prepare_inventory_line(cr, uid, inventory_id, self, context=context)

        inventory_line_obj.create(cr, uid, line_self, context=context)
        inventory_obj.action_done(cr, uid, [inventory_id], context=context)
        return {}

class switchover_product_line(models.Model):
    _name = 'switchover.product.line'

    switchover_id = fields.Many2one(
        string='switchover',
        required=True,
        comodel_name='switchover.product',
        auto_join=True
    )
    product_id = fields.Many2one(
        string='Switch-over Product',
        required=True,
        comodel_name='product.product',
        domain=[('is_product_switchover','=',True)],
        auto_join=True,
        ondelete='restrict',
        oldname='product_switchover'
    )
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
        