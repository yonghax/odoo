from openerp import models, fields, api, _

class stock_picking(models.Model):
    _inherit = 'stock.picking'

    def process_transfer_imported(self):
        super(stock_picking,self).do_new_transfer()

    def do_new_transfer(self, cr, uid, ids, context=None):
        super(stock_picking,self).do_new_transfer(cr, uid, ids, context=context)

        backend_obj = self.pool['prestashop.backend']
        backend_record = backend_obj.search(cr, uid, [], context=context,limit=1)
        backend_record = backend_obj.browse(cr,uid, backend_record, context=context)
        
        if backend_record:
            for pick in self.browse(cr, uid, ids, context=context):
                for operation in pick.pack_operation_ids:
                    backend_record.update_product_stock_qty(context=context, product=operation.product_id)