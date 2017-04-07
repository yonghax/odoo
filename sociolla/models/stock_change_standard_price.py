from datetime import date, datetime
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class change_standard_price(osv.osv_memory):
    
    _inherit = ['stock.change.standard.price']
    
    _columns = {
        'product_id': fields.many2one('product.product', "Product ID"),
        'run_at': fields.datetime('Run at'),
    }

    def do_change_price(self, cr, uid, ids, context=None):
        for item in self.browse(cr, uid, ids, context=context):
            if item.product_id:
                prod_obj = self.pool.get('product.product')
                prod_obj.do_change_standard_price(cr, uid, item.product_id.ids, item.new_price, context)
                item.write({'run_at': datetime.now()})

    def do_change(self, cr, uid, domain=None, context=None):
        obj = self.pool.get('stock.change.standard.price')
        items = obj.browse(
            cr,
            uid,
            obj.search(
                cr,
                uid,
                [('run_at', '=', False)],
                context=context
            ),
            context=context
        )

        for item in items:
            item.do_change_price()

    def change_price(self, cr, uid, ids, context=None):
        """ Changes the Standard Price of Product.
            And creates an account move accordingly.
        @param self: The object pointer.
        @param cr: A database cursor
        @param uid: ID of the user currently logged in
        @param ids: List of IDs selected
        @param context: A standard dictionary
        @return:
        """
        if context is None:
            context = {}
        rec_id = context.get('active_id', False)
        assert rec_id, _('Active ID is not set in Context.')
        data = self.browse(cr, uid, ids, context=context)
        new_price = data[0].new_price
        if context.get("active_model") == 'product.template':
            prod_obj = self.pool.get('product.template')
            rec_ids = prod_obj.browse(cr, uid, rec_id, context=context).product_variant_ids.mapped('id')
        else:
            rec_ids = [rec_id]
        prod_obj = self.pool.get('product.product')
        prod_obj.do_change_standard_price(cr, uid, rec_ids, new_price, context)
        data.write(
        {
            'run_at': datetime.now(), 
            'product_id':rec_ids[0]
        })

        return {'type': 'ir.actions.act_window_close'}