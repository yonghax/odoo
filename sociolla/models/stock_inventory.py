from datetime import date, datetime

from openerp import api, fields, models, SUPERUSER_ID, _
import openerp.addons.decimal_precision as dp
from email.utils import formataddr

import logging
_logger = logging.getLogger(__name__)

class stock_inventory(models.Model):
    _name = 'stock.inventory'
    _inherit = ['stock.inventory', 'mail.thread']
    
    brand_id = fields.Many2one(
        string='Product brand',
        comodel_name='product.brand',
        ondelete='set null'
    )
    account_move_id = fields.Many2many(
        string=u'Journal Created',
        comodel_name='account.move',
        relation='stock_inventory_account_move',
        column1='inventory_id',
        column2='move_id',
    )

    INVENTORY_STATE_SELECTION = [
        ('draft', 'Draft'),
        ('cancel', 'Cancelled'),
        ('to approve', 'To Approve'),
        ('confirm', 'In Progress'),
        ('done', 'Validated'),
    ]
    
    state = fields.Selection(
        string=u'Status',
        selection=INVENTORY_STATE_SELECTION,
        readonly=True, select=True, copy=False
    )
    is_switchover_stock = fields.Boolean(string='Switchover stock',)

    filter = fields.Selection(
        selection = '_get_available_filters', 
        string = 'Inventory of', 
        required=True,
        help="If you do an entire inventory, you can choose 'All Products' and it will prefill the inventory with the current stock.  If you only do some products  "\
            "(e.g. Cycle Counting) you can choose 'Manual Selection of Products' and the system won't propose anything.  You can also let the "\
            "system propose for a single product / lot /... ")
    
    def _get_available_filters(self, cr, uid, context=None):
        res_filter = super(stock_inventory,self)._get_available_filters(cr, uid, context=context)
        res_filter.append(('brand', _('Select one product brand')))
        return res_filter

    def _get_inventory_lines(self, cr, uid, inventory, context=None):
        location_obj = self.pool.get('stock.location')
        product_obj = self.pool.get('product.product')
        location_ids = location_obj.search(cr, uid, [('id', 'child_of', [inventory.location_id.id])], context=context)
        domain = ' location_id in %s'
        args = (tuple(location_ids),)
        if inventory.partner_id:
            domain += ' and owner_id = %s'
            args += (inventory.partner_id.id,)
        if inventory.lot_id:
            domain += ' and lot_id = %s'
            args += (inventory.lot_id.id,)
        if inventory.product_id:
            domain += ' and product_id = %s'
            args += (inventory.product_id.id,)
        if inventory.package_id:
            domain += ' and package_id = %s'
            args += (inventory.package_id.id,)
        if inventory.brand_id:
            domain += ' and product_brand_id = %s'
            args += (inventory.brand_id.id,)

        cr.execute('''
           SELECT sq.product_id, sum(sq.qty) as product_qty, sq.location_id, sq.lot_id as prod_lot_id, sq.package_id, sq.owner_id as partner_id, pp.product_brand_id as brand_id
           FROM stock_quant sq
           INNER JOIN 
           (
               SELECT pp.id, pt.product_brand_id 
               FROM product_product pp
               INNER JOIN product_template pt on pp.product_tmpl_id = pt.id
           ) pp ON pp.id = sq.product_id
           WHERE''' + domain + '''
           GROUP BY product_id, location_id, lot_id, package_id, partner_id, product_brand_id
        ''', args)
        vals = []
        for product_line in cr.dictfetchall():
            #replace the None the dictionary by False, because falsy values are tested later on
            for key, value in product_line.items():
                if not value:
                    product_line[key] = False
            product_line['inventory_id'] = inventory.id
            product_line['theoretical_qty'] = product_line['product_qty']
            if product_line['product_id']:
                product = product_obj.browse(cr, uid, product_line['product_id'], context=context)
                product_line['product_uom_id'] = product.uom_id.id
            vals.append(product_line)
        return vals

    @api.one
    def request_approval(self):
        user_obj = self.env['res.users']
        group_obj = self.env['res.groups']
        mail_obj = self.env['mail.mail']
        message_obj = self.env['mail.message']
        module_category_obj = self.env['ir.module.category']

        user_stock_reviewer = self.env.ref('sociolla.group_stock_reviewer').users
        subtype_id = self.env.ref('sociolla.stock_adjustment_approval').id

        for user_manager in user_stock_reviewer:
            msg = message_obj.create({
                'message_type': 'comment',
                'subtype_id': 1,
                'subject' : 'Request Approval Stock Adjustment',
                'res_id': self.id,
                'body': 'Stock adjustment: %s , needs your approval to validate.' % (self.name),
                'email_from': formataddr((self.env.user.name, self.env.user.email)),
                'model': 'stock.inventory',
                'partner_ids': [(4, [user_manager.partner_id.id])],
            })
            user_manager.partner_id.with_context(auto_delete=True)._notify(msg, force_send=True, user_signature=True)
        
        self.write({'state': 'to approve'})

class stock_inventory_line(models.Model):
    _inherit = 'stock.inventory.line'
    
    product_brand_id = fields.Many2one(string=u'Brand', compute='get_product_brand', comodel_name='product.brand')
    standard_price = fields.Float(string=u'Cost')
    theoretical_qty = fields.Float('Theoretical Quantity', compute='_compute_theoretical_qty',digits=dp.get_precision('Product Unit of Measure'), readonly=True, store=True)
    total_cost = fields.Float(
        string=u'Total Cost',
        compute='_compute_total_cost'
    )

    @api.depends('product_id', 'product_qty', 'standard_price')
    @api.one
    def _compute_total_cost(self):
        if self.product_id:
            diff = self.theoretical_qty - self.product_qty
            if diff:
                self.total_cost = diff * self.standard_price
                self.total_cost = -self.total_cost

    def _get_quants(self):
        return self.env['stock.quant'].search([
            ('company_id', '=', self.inventory_id.company_id.id),
            ('location_id', '=', self.location_id.id),
            ('lot_id', '=', self.prod_lot_id.id),
            ('product_id', '=', self.product_id.id),
            ('owner_id', '=', self.partner_id.id),
            ('package_id', '=', self.package_id.id)])

    @api.depends('product_id')
    @api.one
    def get_product_brand(self):
        if self.product_id:
            self.product_brand_id = self.product_id.product_tmpl_id.product_brand_id.id

    @api.onchange('product_id')
    def onchange_product(self):
        res = {}
        # If no UoM or incorrect UoM put default one from product
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id
            res['domain'] = {'product_uom_id': [('category_id', '=', self.product_id.uom_id.category_id.id)]}
            quants = self._get_quants()
            if quants and len(quants) > 0 and quants[0].cost != 0:
                self.standard_price = quants[0].cost
            else:
                self.standard_price = self.product_id.standard_price
        return res

    @api.one
    @api.depends('location_id', 'product_id', 'package_id', 'product_uom_id', 'company_id', 'prod_lot_id', 'partner_id')
    def _compute_theoretical_qty(self):
        if not self.product_id:
            self.theoretical_qty = 0
            return
        theoretical_qty = sum([x.qty for x in self._get_quants()])
        if theoretical_qty and self.product_uom_id and self.product_id.uom_id != self.product_uom_id:
            theoretical_qty = self.product_id.uom_id._compute_quantity(theoretical_qty, self.product_uom_id)
        self.theoretical_qty = theoretical_qty

    @api.onchange('product_id', 'location_id', 'product_uom_id', 'prod_lot_id', 'partner_id', 'package_id')
    def onchange_quantity_context(self):
        if self.product_id and self.location_id and self.product_id.uom_id.category_id == self.product_uom_id.category_id:  # TDE FIXME: last part added because crash
            if self.location_id.company_id:
                self.company_id = self.location_id.company_id
            self._compute_theoretical_qty()
            self.product_qty = self.theoretical_qty

    def _resolve_inventory_line(self, cr, uid, inventory_line, context=None):
        stock_move_obj = self.pool.get('stock.move')
        quant_obj = self.pool.get('stock.quant')
        diff = inventory_line.theoretical_qty - inventory_line.product_qty
        if not diff:
            return
        #each theorical_lines where difference between theoretical and checked quantities is not 0 is a line for which we need to create a stock move
        vals = {
            'name': _('INV:') + (inventory_line.inventory_id.name or ''),
            'product_id': inventory_line.product_id.id,
            'product_uom': inventory_line.product_uom_id.id,
            'date': inventory_line.inventory_id.date,
            'company_id': inventory_line.inventory_id.company_id.id,
            'inventory_id': inventory_line.inventory_id.id,
            'state': 'confirmed',
            'restrict_lot_id': inventory_line.prod_lot_id.id,
            'restrict_partner_id': inventory_line.partner_id.id,
            'is_switchover_stock': inventory_line.inventory_id.is_switchover_stock,
        }
        inventory_location_id = inventory_line.product_id.property_stock_inventory.id


        if inventory_line.location_id.usage == 'internal':
            vals['price_unit'] = inventory_line.standard_price
            # ctx = dict(context, force_valuation_amount=inventory_line.standard_price)

        if diff < 0:
            #found more than expected
            vals['location_id'] = inventory_location_id
            vals['location_dest_id'] = inventory_line.location_id.id
            vals['product_uom_qty'] = -diff
        else:
            #found less than expected
            vals['location_id'] = inventory_line.location_id.id
            vals['location_dest_id'] = inventory_location_id
            vals['product_uom_qty'] = diff
        move_id = stock_move_obj.create(cr, uid, vals, context=context)
        move = stock_move_obj.browse(cr, uid, move_id, context=context)
        if diff > 0:
            domain = [('qty', '>', 0.0), ('package_id', '=', inventory_line.package_id.id), ('lot_id', '=', inventory_line.prod_lot_id.id), ('location_id', '=', inventory_line.location_id.id)]
            preferred_domain_list = [[('reservation_id', '=', False)], [('reservation_id.inventory_id', '!=', inventory_line.inventory_id.id)]]
            quants = quant_obj.quants_get_preferred_domain(cr, uid, move.product_qty, move, domain=domain, preferred_domain_list=preferred_domain_list)
            quant_obj.quants_reserve(cr, uid, quants, move, context=context)
        elif inventory_line.package_id:
            stock_move_obj.action_done(cr, uid, move_id, context=context)
            quants = [x.id for x in move.quant_ids]
            quant_obj.write(cr, SUPERUSER_ID, quants, {'package_id': inventory_line.package_id.id}, context=context)
            res = quant_obj.search(cr, uid, [('qty', '<', 0.0), ('product_id', '=', move.product_id.id),
                                    ('location_id', '=', move.location_dest_id.id), ('package_id', '!=', False)], limit=1, context=context)
            if res:
                for quant in move.quant_ids:
                    if quant.location_id.id == move.location_dest_id.id: #To avoid we take a quant that was reconcile already
                        quant_obj._quant_reconcile_negative(cr, uid, quant, move, context=context)
        return move_id