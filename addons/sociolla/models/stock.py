from openerp import api, fields, models, _
from openerp.tools.float_utils import float_compare, float_round

class stock_picking(models.Model):
    _inherit = 'stock.picking'

    vendor_id = fields.Many2one(
        string='Vendor ID',
        comodel_name='res.partner',
    )

    @api.cr_uid_ids_context
    def do_prepare_partial(self, cr, uid, picking_ids, context=None):
        context = context or {}
        pack_operation_obj = self.pool.get('stock.pack.operation')
        product_obj = self.pool.get('product.product')

        #get list of existing operations and delete them
        existing_package_ids = pack_operation_obj.search(cr, uid, [('picking_id', 'in', picking_ids)], context=context)
        if existing_package_ids:
            pack_operation_obj.unlink(cr, uid, existing_package_ids, context)
        for picking in self.browse(cr, uid, picking_ids, context=context):
            forced_qties = {}  # Quantity remaining after calculating reserved quants
            picking_quants = []
            #Calculate packages, reserved quants, qtys of this picking's moves
            for move in picking.move_lines:
                if move.state not in ('assigned', 'confirmed', 'waiting'):
                    continue
                move_quants = move.reserved_quant_ids
                picking_quants += move_quants
                forced_qty = (move.state == 'assigned') and move.product_qty - sum([x.qty for x in move_quants]) or 0
                #if we used force_assign() on the move, or if the move is incoming, forced_qty > 0
                if float_compare(forced_qty, 0, precision_rounding=move.product_id.uom_id.rounding) > 0:
                    if forced_qties.get(move.product_id):
                        forced_qties[move.product_id] += forced_qty
                    else:
                        forced_qties[move.product_id] = forced_qty
            for vals in self._prepare_pack_ops(cr, uid, picking, picking_quants, forced_qties, context=context):
                vals['fresh_record'] = False

                product = product_obj.browse(cr, uid,[vals['product_id']],context=context)
                if product.product_brand_id.categ_id.name == 'Consignment':
                    vals['owner_id'] = picking.vendor_id.id
                
                pack_operation_obj.create(cr, uid, vals, context=context)
        #recompute the remaining quantities all at once
        self.do_recompute_remaining_quantities(cr, uid, picking_ids, context=context)
        self.write(cr, uid, picking_ids, {'recompute_pack_op': False}, context=context)

class stock_inventory(models.Model):
    _inherit = ['stock.inventory']
    
    brand_id = fields.Many2one(
        string='Product brand',
        help="Select product brand",
        comodel_name='product.brand',
    )

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