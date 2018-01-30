from openerp import api, fields, models, _

class stock_inventory_wizard(models.TransientModel):
    
    _inherit = ['wizard.valuation.history']
    
    filter_type = fields.Selection(
        string=u'Filter by',
        default='brand',
        selection=[('brand', 'Product Brand'), ('product', 'Product')]
    )
    product_brand_ids = fields.Many2many(
        comodel_name='product.brand', 
        relation='stock_inventory_wizard_product_brand', 
        column1='wizard_id', 
        column2='product_brand_id', 
        string='Filter Product Brand', 
    )
    product_product_ids = fields.Many2many(
        string=u'Filter Product',
        comodel_name='product.product',
        relation='stock_inventory_wizard_product_product',
        column1='wizard_id',
        column2='product_id',
    )

    @api.multi
    def open_table(self):
        self.ensure_one()
        ctx = dict(
            self._context,
            history_date = self.date,
            search_default_group_by_product=True,
            search_default_group_by_location=True,)

        action = self.env['ir.model.data'].xmlid_to_object('stock_account.action_stock_history')
        if not action:
            action = {
                'view_type': 'form',
                'view_mode': 'tree,graph,pivot',
                'res_model': 'stock.history',
                'type': 'ir.actions.act_window',
            }
        else:
            action = action[0].read()[0]

        domain = "('date', '<=', '" + self.date + "')"
        if self.filter_type == 'product':
            print 'product_product_ids.product_id.ids: ' , self.product_product_ids.ids
            domain += ",('product_id', 'in', %s)" % (self.product_product_ids.ids)
        elif self.filter_type == 'brand':
            print 'product_brand_ids.product_brand_id.ids: ' , self.product_brand_ids.ids
            domain += ",('product_brand_id', 'in', %s)" % (self.product_brand_ids.ids)

        action['domain'] = "[%s]" % (domain)
        action['name'] = _('Stock Value At Date')
        action['context'] = ctx
        return action