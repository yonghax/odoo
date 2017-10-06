from datetime import date, datetime

from openerp import api, fields, models, SUPERUSER_ID, _
from openerp.exceptions import UserError
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT, DEFAULT_SERVER_DATE_FORMAT
from openerp.tools.float_utils import float_compare, float_round

class stock_inventory(models.Model):
    _inherit = ['stock.inventory']
    
    brand_id = fields.Many2one(
        string='Product brand',
        help="Select product brand",
        comodel_name='product.brand',
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

    def auto_proses_action_done(self, cr, uid, domain=None, context=None):
        obj = self.pool.get('stock.inventory')
        items = obj.browse(
            cr,
            uid,
            [887],
            context=context
        )

        for item in items:
            item.action_done()

class stock_inventory_line(models.Model):
    _inherit = 'stock.inventory.line'

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

class stock_pack_operation(models.Model):
    _inherit = ['stock.pack.operation']
    barcode = fields.Char(string=u'Barcode',compute='_get_barcode')
    
    def _get_barcode(self):
        for data in self:
            if data.product_id:
                data.barcode = data.product_id.barcode

class stock_move(models.Model):
    _inherit = 'stock.move'
    
    is_switchover_stock = fields.Boolean(string='Switchover stock')

class stock_quant(models.Model):
    _inherit = 'stock.quant'

    is_switchover_stock = fields.Boolean(string='Switchover stock')

    def _quant_create(self, cr, uid, qty, move, lot_id=False, owner_id=False, src_package_id=False, dest_package_id=False,
                      force_location_from=False, force_location_to=False, context=None):
        '''Create a quant in the destination location and create a negative quant in the source location if it's an internal location.
        '''
        if context is None:
            context = {}
        price_unit = self.pool.get('stock.move').get_price_unit(cr, uid, move, context=context)
        location = force_location_to or move.location_dest_id
        rounding = move.product_id.uom_id.rounding
        vals = {
            'product_id': move.product_id.id,
            'location_id': location.id,
            'qty': float_round(qty, precision_rounding=rounding),
            'cost': price_unit,
            'history_ids': [(4, move.id)],
            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'company_id': move.company_id.id,
            'lot_id': lot_id,
            'owner_id': owner_id,
            'package_id': dest_package_id,
            'is_switchover_stock': move.is_switchover_stock,
        }
        if move.location_id.usage == 'internal':
            #if we were trying to move something from an internal location and reach here (quant creation),
            #it means that a negative quant has to be created as well.
            negative_vals = vals.copy()
            negative_vals['location_id'] = force_location_from and force_location_from.id or move.location_id.id
            negative_vals['qty'] = float_round(-qty, precision_rounding=rounding)
            negative_vals['cost'] = price_unit
            negative_vals['negative_move_id'] = move.id
            negative_vals['package_id'] = src_package_id
            negative_quant_id = self.create(cr, SUPERUSER_ID, negative_vals, context=context)
            vals.update({'propagated_from_id': negative_quant_id})

        picking_type = move.picking_id and move.picking_id.picking_type_id or False
        if lot_id and move.product_id.tracking == 'serial' and (not picking_type or (picking_type.use_create_lots or picking_type.use_existing_lots)):
            if qty != 1.0:
                raise UserError(_('You should only receive by the piece with the same serial number'))

        #create the quant as superuser, because we want to restrict the creation of quant manually: we should always use this method to create quants
        quant_id = self.create(cr, SUPERUSER_ID, vals, context=context)
        quant = self.browse(cr, uid, quant_id, context=context)
        if move.product_id.valuation == 'real_time':
            self._account_entry_move(cr, uid, [quant], move, context)

            # If the precision required for the variable quant cost is larger than the accounting
            # precision, inconsistencies between the stock valuation and the accounting entries
            # may arise.
            # For example, a box of 13 units is bought 15.00. If the products leave the
            # stock one unit at a time, the amount related to the cost will correspond to
            # round(15/13, 2)*13 = 14.95. To avoid this case, we split the quant in 12 + 1, then
            # record the difference on the new quant.
            # We need to make sure to able to extract at least one unit of the product. There is
            # an arbitrary minimum quantity set to 2.0 from which we consider we can extract a
            # unit and adapt the cost.
            curr_rounding = move.company_id.currency_id.rounding
            cost_rounded = float_round(quant.cost, precision_rounding=curr_rounding)
            cost_correct = cost_rounded
            if float_compare(quant.product_id.uom_id.rounding, 1.0, precision_digits=1) == 0\
                    and float_compare(quant.qty * quant.cost, quant.qty * cost_rounded, precision_rounding=curr_rounding) != 0\
                    and float_compare(quant.qty, 2.0, precision_rounding=quant.product_id.uom_id.rounding) >= 0:
                qty = quant.qty
                cost = quant.cost
                quant_correct = quant_obj._quant_split(cr, uid, quant, quant.qty - 1.0, context=context)
                cost_correct += (qty * cost) - (qty * cost_rounded)
                quant_obj.write(cr, SUPERUSER_ID, [quant.id], {'cost': cost_rounded}, context=context)
                quant_obj.write(cr, SUPERUSER_ID, [quant_correct.id], {'cost': cost_correct}, context=context)
        return quant

    def _account_entry_move(self, cr, uid, quants, move, context=None):
        if not move.is_switchover_stock:
            super(stock_quant, self)._account_entry_move(cr, uid, quants, move, context=context)
        
        return False