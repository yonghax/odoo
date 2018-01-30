import logging

from ...backend import prestashop
from ...unit.import_synchronizer import PrestashopImportSynchronizer
from openerp.addons.connector.unit.backend_adapter import BackendAdapter

import MySQLdb
import MySQLdb.cursors as cursors

_logger = logging.getLogger(__name__)

@prestashop
class ProductCombinationRecordImport(PrestashopImportSynchronizer):
    _model_name = 'prestashop.product.combination'
      
    def _after_import(self, erp_id):
        host = self.env['ir.config_parameter'].get_param('mysql.host')
        user = self.env['ir.config_parameter'].get_param('mysql.user')
        passwd = self.env['ir.config_parameter'].get_param('mysql.passwd')
        dbname = self.env['ir.config_parameter'].get_param('mysql.dbname')

        db = MySQLdb.connect(host, user, passwd, dbname, cursorclass=MySQLdb.cursors.DictCursor)
        cur = db.cursor()

        query = """
select pa.active_att
from ps_product_attribute pa
where pa.id_product_attribute = %s 
        """ % self.prestashop_id 

        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        db.close()

        for row in rows:
            erp_id.openerp_id.write({'active': bool(int(row['active_att']))})

    def _import_dependencies(self):
        record = self.prestashop_record
        option_values = record.get('associations', {}).get(
            'product_option_values', {}).get('product_option_values', [])
        if not isinstance(option_values, list):
            option_values = [option_values]
        backend_adapter = self.unit_for(
            BackendAdapter,
            'prestashop.product.attribute.value'
        )
        for option_value in option_values:
            option_value = backend_adapter.read(option_value['id'])
            self._import_dependency(
                option_value['id'],
                'prestashop.product.attribute.value'
            )

    def unit_price_impact(self, erp_id):
        record = self.prestashop_record
        _logger.debug("Record pour extra price")
        _logger.debug(record)
        _logger.debug(erp_id)
        unit_price_impact = float(record['unit_price_impact']) or 0.0
        _logger.debug("Unit price impact : %s ", 
                                            str(unit_price_impact))
                                            
        main_template = erp_id.product_tmpl_id
        _logger.debug("Template : %s ")
        _logger.debug(main_template)
        
        option_values = record.get('associations', {}).get(
            'product_option_values', {}).get('product_option_value', [])
        _logger.debug(option_values)
        
        for option_value_object in option_values:
            _logger.debug(option_value_object)

