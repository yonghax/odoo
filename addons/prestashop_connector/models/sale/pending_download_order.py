from datetime import date, datetime
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class pending_download_order(osv.osv_memory):
    _name = 'pending.download.order'

    _columns={
        'prestashop_id_order': fields.integer('Prestashop ID Order'),
        'run_at': fields.datetime('Run at')
    }