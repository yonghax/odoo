from openerp import models, fields, api, _
from openerp import SUPERUSER_ID

class stock_picking(models.Model):
    _inherit = 'stock.picking'

    def do_transfer(self, cr, uid, ids, context=None):
        super(stock_picking,self).do_transfer(cr, uid, ids, context=context)

        backend_obj = self.pool['prestashop.backend']
        backend_record = backend_obj.search(cr, SUPERUSER_ID, [], context=context,limit=1)
        backend_record = backend_obj.browse(cr,SUPERUSER_ID, backend_record, context=context)
        
        if backend_record:
            for pick in self.browse(cr, SUPERUSER_ID, ids, context=context):
                if pick.state == 'done' and pick.date_done and pick.picking_type_code == 'incoming':
                    for operation in pick.pack_operation_ids:
                        if operation.product_qty == operation.qty_done:
                            backend_record.update_product_stock_qty(context=context, product=operation.product_id)

class stock_quant(models.Model):
    _inherit = 'stock.quant'
    
    def _account_entry_move(self, cr, uid, quants, move, context=None):
        super(stock_quant,self)._account_entry_move(cr, SUPERUSER_ID, quants, move, context=context)