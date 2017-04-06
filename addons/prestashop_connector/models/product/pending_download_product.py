from datetime import date, datetime
from openerp.osv import fields, osv
from openerp.tools.translate import _
import openerp.addons.decimal_precision as dp

class pending_download_product(osv.osv_memory):
    _name = 'pending_download_product'

    _columns={
        'prestashop_product_id': fields.integer('Prestashop Product Header'),
    }