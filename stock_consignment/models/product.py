from openerp import api, fields, models, SUPERUSER_ID, _

class product_category(models.Model):
    _inherit = 'product.category'

    category_purchase_type = fields.Selection(
        string='Purchase Type', 
        required=False, 
        default=False,
        selection=[('direct', 'Direct Purchase'),('cons', 'Consignment')])

class product_template(models.Model):
    _inherit = 'product.template'

    product_purchase_type = fields.Selection(
        string='Purchase Type', 
        required=True,
        default=False,
        selection=[('direct', 'Direct Purchase'),('cons', 'Consignment')],
        oldname='product_purchaes_type')

    @api.onchange('product_brand_id')
    def _set_purchase_type(self):
        if self.product_brand_id:
            self.product_purchase_type = self.product_brand_id.purchase_type

    @api.multi
    def _get_purchase_type(self):
        return self.product_purchase_type or self.categ_id.category_purchase_type

    def do_change_standard_price(self, cr, uid, ids, new_price, context=None):
        """ Changes the Standard Price of Product and creates an account move accordingly."""
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('account.move')
        if context is None:
            context = {}
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        loc_ids = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('company_id', '=', user_company_id)])
        for rec_id in ids:
            c = context.copy()
            product = self.browse(cr, uid, rec_id, context=c)
            if product._get_purchase_type() != 'cons': # if purchase type = consignment, dont need to create journal entry
                datas = self.get_product_accounts(cr, uid, rec_id, context=context)
                for location in location_obj.browse(cr, uid, loc_ids, context=context):
                    c.update({'location': location.id, 'compute_child': False})
                    diff = product.standard_price - new_price
                    if not diff:
                        raise UserError(_("No difference between standard price and new price!"))
                    for prod_variant in product.product_variant_ids:
                        qty = prod_variant.qty_available
                        if qty:
                            # Accounting Entries
                            amount_diff = abs(diff * qty)
                            if diff * qty > 0:
                                debit_account_id = datas['expense'].id
                                credit_account_id = datas['stock_valuation'].id
                            else:
                                debit_account_id = datas['stock_valuation'].id
                                credit_account_id = datas['expense'].id

                            lines = [(0, 0, {'name': _('Standard Price changed'),
                                            'account_id': debit_account_id,
                                            'debit': amount_diff,
                                            'credit': 0,
                                            }),
                                    (0, 0, {
                                            'name': _('Standard Price changed'),
                                            'account_id': credit_account_id,
                                            'debit': 0,
                                            'credit': amount_diff,
                                            })]
                            move_vals = {
                                'journal_id': datas['stock_journal'].id,
                                'company_id': location.company_id.id,
                                'line_ids': lines,
                            }
                            move_id = move_obj.create(cr, uid, move_vals, context=context)
                            move_obj.post(cr, uid, [move_id], context=context)
            self.write(cr, uid, rec_id, {'standard_price': new_price})
        return True

class ProductBrand(models.Model):
    _inherit = 'product.brand'

    purchase_type = fields.Selection(
        string='Purchase Type', 
        required=False, 
        default=False,
        selection=[('direct', 'Direct Purchase'),('cons', 'Consignment')])

    partner_id = fields.Many2one(
        'res.partner',
        string='Partner',
        help='Select a partner for this brand if any.',
        domain="[('supplier','=',True)]",
        ondelete='restrict'
    )

    @api.one
    @api.constrains('partner_id')
    def _validate_partner_required(self):
        if not self.partner_id and self.purchase_type == 'cons':
            raise models.ValidationError('Partner supplier is required!')

class Product(models.Model):
    _inherit = 'product.product'

    def do_change_standard_price(self, cr, uid, ids, new_price, context=None):
        """ Changes the Standard Price of Product and creates an account move accordingly."""
        location_obj = self.pool.get('stock.location')
        move_obj = self.pool.get('account.move')
        if context is None:
            context = {}
        user_company_id = self.pool.get('res.users').browse(cr, uid, uid, context=context).company_id.id
        loc_ids = location_obj.search(cr, uid, [('usage', '=', 'internal'), ('company_id', '=', user_company_id)])
        for rec_id in ids:
            c = context.copy()
            product = self.browse(cr, uid, rec_id, context=c)
            if product.product_tmpl_id._get_purchase_type() != 'cons': # if purchase type = consignment, dont need to create journal entry
                for location in location_obj.browse(cr, uid, loc_ids, context=context):
                    c.update({'location': location.id, 'compute_child': False})
                    datas = self.pool['product.template'].get_product_accounts(cr, uid, product.product_tmpl_id.id, context=context)
                    diff = product.standard_price - new_price
                    if not diff:
                        raise UserError(_("No difference between standard price and new price!"))
                    qty = product.qty_available
                    if qty:
                        # Accounting Entries
                        amount_diff = abs(diff * qty)
                        if diff * qty > 0:
                            debit_account_id = datas['expense'].id
                            credit_account_id = datas['stock_valuation'].id
                        else:
                            debit_account_id = datas['stock_valuation'].id
                            credit_account_id = datas['expense'].id

                        lines = [(0, 0, {'name': _('Standard Price changed'),
                                        'account_id': debit_account_id,
                                        'debit': amount_diff,
                                        'credit': 0,
                                        }),
                                (0, 0, {
                                        'name': _('Standard Price changed'),
                                        'account_id': credit_account_id,
                                        'debit': 0,
                                        'credit': amount_diff,
                                        })]
                        move_vals = {
                            'journal_id': datas['stock_journal'].id,
                            'company_id': location.company_id.id,
                            'line_ids': lines,
                        }
                        move_id = move_obj.create(cr, uid, move_vals, context=context)
                        move_obj.post(cr, uid, [move_id], context=context)
            self.write(cr, uid, rec_id, {'standard_price': new_price})
        return True

class product_supplierinfo(models.Model):
    _inherit = ['product.supplierinfo']

    @api.multi
    def write(self, vals):
        res = super(product_supplierinfo, self).write(vals)
        if 'price' in vals or 'discount' in vals:
            for rec in self:
                rec.invalidate_product_standard_price()

        return res
        
    @api.model
    def create(self, vals):
        record = super(product_supplierinfo, self).create(vals)
        record.invalidate_product_standard_price()

        return record

    @api.multi
    def invalidate_product_standard_price(self):
        product_tmpl = self.product_tmpl_id

        if product_tmpl and product_tmpl._get_purchase_type() == 'cons' and product_tmpl.cost_method == 'standard':
            price_after_margin = self.price * (1 - (self.discount or 0.0) / 100.0)
            product_tmpl.sudo().do_change_standard_price(price_after_margin)
            product_tmpl.sudo().write({'lst_price': self.price}) 
