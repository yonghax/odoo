# -*- coding: utf-8 -*-

from decimal import Decimal

from openerp.tools.translate import _
from openerp.addons.connector.unit.mapper import (
    mapping,
    ImportMapper,
    ExportMapper
)
from ..backend import prestashop
from ..connector import add_checkpoint
from backend_adapter import GenericAdapter
from backend_adapter import PrestaShopCRUDAdapter
from openerp.addons.connector_ecommerce.unit.sale_order_onchange import (
    SaleOrderOnChange)
from openerp.addons.connector.connector import Binder
from openerp.addons.connector.unit.mapper import only_create



class PrestashopImportMapper(ImportMapper):
    
    #get_openerp_id is deprecated use the binder intead
    #we should have only 1 way to map the field to avoid error
    def get_openerp_id(self, model, prestashop_id):
        '''
        Returns an openerp id from a model name and a prestashop_id.

        This permits to find the openerp id through the external application
        model in Erp.
        '''
        binder = self.binder_for(model)
        erp_ps_id = binder.to_openerp(prestashop_id)
        if erp_ps_id is None:
            return None

        model = self.session.pool.get(model)
        erp_ps_object = model.read(
            self.session.cr,
            self.session.uid,
            erp_ps_id,
            ['openerp_id'],
            context=self.session.context
        )
        return erp_ps_object['openerp_id'][0]

def normalize_datetime(field):
    """Change a invalid date which comes from Magento, if
    no real date is set to null for correct import to
    OpenERP"""
    def modifier(self, record, to_attr):
        if record[field] == '0000-00-00 00:00:00':
            return None
        return record[field]
    return modifier

class PrestashopExportMapper(ExportMapper):
    def _map_direct(self, record, from_attr, to_attr):
        res = super(PrestashopExportMapper, self)._map_direct(record,
                                                              from_attr,
                                                              to_attr)
        column = self.model._all_columns[from_attr].column
        if column._type == 'boolean':
            return res and 1 or 0
        return res


class TranslationPrestashopExportMapper(PrestashopExportMapper):

    def convert(self, records_by_language, fields=None):
        self.records_by_language = records_by_language
        first_key = records_by_language.keys()[0]
        self._convert(records_by_language[first_key], fields=fields)
        self._data.update(self.convert_languages(self.translatable_fields))

    def convert_languages(self, translatable_fields):
        res = {}
        for from_attr, to_attr in translatable_fields:
            value = {'language': []}
            for language_id, record in self.records_by_language.items():
                value['language'].append({
                    'attrs': {'id': str(language_id)},
                    'value': record[from_attr]
                })
            res[to_attr] = value
        return res