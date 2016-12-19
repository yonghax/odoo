from openerp import models, fields, api, _
from openerp import SUPERUSER_ID

class stock_picking(models.Model):
    _inherit = 'stock.picking'

class stock_move(models.Model):
    _inherit = 'stock.move'

    def action_done(self, cr, uid, ids, context=None):
        if super(stock_move,self).action_done(cr, uid, ids, context=context):
            backend_obj = self.pool['prestashop.backend']
            backend_record = backend_obj.search(cr, SUPERUSER_ID, [], context=context,limit=1)
            backend_record = backend_obj.browse(cr,SUPERUSER_ID, backend_record, context=context)

            if backend_record:
                for move in self.browse(cr, uid, ids, context=context):
                    pick = move.picking_id
                    if move.state == 'done' and (pick and (pick.picking_type_code == 'incoming' or (pick.picking_type_code == 'outgoing' and move.origin_returned_move_id))):
                        backend_record.update_product_stock_qty(context=context, product=move.product_id)

class stock_quant(models.Model):
    _inherit = 'stock.quant'
    
    def _account_entry_move(self, cr, uid, quants, move, context=None):
        super(stock_quant,self)._account_entry_move(cr, SUPERUSER_ID, quants, move, context=context)