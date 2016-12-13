from openerp import api, fields, models, _

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