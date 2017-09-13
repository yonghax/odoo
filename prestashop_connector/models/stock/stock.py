from openerp import models, fields, api, _
from openerp import SUPERUSER_ID
from datetime import datetime
from openerp.tools import DEFAULT_SERVER_DATETIME_FORMAT

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
                    if pick and (pick.picking_type_code == 'outgoing' and not move.origin_returned_move_id):
                        continue
                        
                    if move.state == 'done' or (pick and (pick.picking_type_code == 'incoming' or (pick.picking_type_code == 'outgoing' and move.origin_returned_move_id))):
                        backend_record.update_product_stock_qty(context=context, product=move.product_id)

    def scheduler_push_qty(self, cr, uid, domain=None, context=None):
        ps_backend_obj = self.pool.get('prestashop.backend')
        ps_backends = ps_backend_obj.browse(
            cr,
            uid, 
            [1], 
            context=context
        )
        for ps_backend in ps_backends:
            if ps_backend and ps_backend.export_qty_since:
                move_obj = self.pool.get('stock.move')
                moves = move_obj.browse(
                    cr,
                    uid,
                    move_obj.search(
                        cr,
                        uid,
                        [('date', '>=', ps_backend.export_qty_since), ('state', '=', 'done'), ('location_dest_id', '!=', 9)]
                    )
                )

                for move in moves:
                    ps_backend.update_product_stock_qty(context=context, product=move.product_id)
         
            ps_backend_obj.write(
                cr,
                uid,
                ps_backend.id,
                {'import_partners_since': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT)},
            )


class stock_quant(models.Model):
    _inherit = 'stock.quant'
    
    def _account_entry_move(self, cr, uid, quants, move, context=None):
        super(stock_quant,self)._account_entry_move(cr, SUPERUSER_ID, quants, move, context=context)