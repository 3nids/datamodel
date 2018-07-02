import unittest
import os

import psycopg2
import psycopg2.extras
import decimal
from time import sleep

from utils import DbTestBase

class TestTriggers(unittest.TestCase, DbTestBase):


    @classmethod
    def tearDownClass(cls):
        cls.conn.rollback()


    @classmethod
    def setUpClass(cls):
        pgservice=os.environ.get('PGSERVICE')
        if not pgservice:
          pgservice='pg_qgep'
        cls.conn = psycopg2.connect("service={service}".format(service=pgservice))


    # - correct update with 1 old outlet and 1 new outlet and 0 old inlet and 0 new inlet
    #   -> updated structure
    #   -> updated reach
    #   -> updated reach_point
    #   -> deleted in quarantene
    def test_update_with_outlet(self):
        # obj_id from the test data
        obj_id = 'ch13p7mzMA000012'

        # change remark from 'Strasseneinlauf' to 'Strassenauslauf'
        # change co_material from 233 to 3015
        row = {
                'remark': 'Strassenauslauf',
                'co_material': 3015,
                'outlet_1_material': 5081,
                'outlet_1_dimension_mm': 160,
                'outlet_1_depth_m': 100,
                'photo1' : 'funky_selfie.png'
        }

        # update
        self.update('vw_manhole', row, obj_id, 'qgep_import')

        # it should be in the live table qgep_od.wastewater_structure
        row = self.select( 'wastewater_structure', obj_id, 'qgep_od')
        self.assertIsNotNone( row )
        self.assertEqual( row['remark'], 'Strassenauslauf')

        # it should be in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertEqual( row['co_material'], 3015)
        self.assertEqual( row['remark'], 'Strassenauslauf')

        # it should be in the live table qgep_od.reach and qgep_od.reach_point
        cur = self.cursor()
        cur.execute("SELECT re.material, re.clear_height, rp.level, ws.co_level\
            FROM {schema}.reach re\
            LEFT JOIN {schema}.reach_point rp ON rp.obj_id = re.fk_reach_point_from\
            LEFT JOIN {schema}.wastewater_networkelement wn ON wn.obj_id = rp.fk_wastewater_networkelement\
            LEFT JOIN {schema}.vw_qgep_wastewater_structure ws ON ws.obj_id = wn.fk_wastewater_structure\
            WHERE ws.obj_id = '{obj_id}'".format(schema='qgep_od', obj_id=obj_id))
        row = cur.fetchone()
        self.assertIsNotNone( row )
        self.assertEqual( row['material'], 5081)
        self.assertEqual( row['clear_height'], 160)
        self.assertEqual( row['level'], decimal.Decimal('301.700'))

        # the photo should be in the live table qgep_od.file
        row = self.select( 'file', obj_id, 'qgep_od')
        cur = self.cursor()
        cur.execute("SELECT *\
            FROM {schema}.file\
            WHERE object = '{obj_id}'".format(schema='qgep_od', obj_id=obj_id))
        row = cur.fetchone()
        self.assertEqual( row['identifier'], 'funky_selfie.png')

        # it shouldn't be in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNone( row )


    # - incorrect update with a wrong cover material
    #   -> updated reach
    #   -> updated reach_point
    #   -> still in quarantene (inlet_okay t, outlet_okay t but structure_okay f)
    #   - update material
    #     -> updated structure
    #     -> deleted in quarantene
    def test_update_with_wrong_material(self):
        # obj_id from the test data
        obj_id = 'ch13p7mzMA000012'

        # change co_material from 233 to 666, what not exists in the table qgep_vl.cover_material
        row = {
                'co_material': 666,
                'outlet_1_material': 5081
        }

        # update
        self.update('vw_manhole', row, obj_id, 'qgep_import')

        # it should be in the live table qgep_od.reach and qgep_od.reach_point
        cur = self.cursor()
        cur.execute("SELECT re.material, re.clear_height, rp.level, ws.co_level\
            FROM {schema}.reach re\
            LEFT JOIN {schema}.reach_point rp ON rp.obj_id = re.fk_reach_point_from\
            LEFT JOIN {schema}.wastewater_networkelement wn ON wn.obj_id = rp.fk_wastewater_networkelement\
            LEFT JOIN {schema}.vw_qgep_wastewater_structure ws ON ws.obj_id = wn.fk_wastewater_structure\
            WHERE ws.obj_id = '{obj_id}'".format(schema='qgep_od', obj_id=obj_id))
        row = cur.fetchone()
        self.assertIsNotNone( row )
        self.assertEqual( row['material'], 5081)

        # it shouldn't be updated in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertNotEqual( row['co_material'], 666)

        # it should be in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNotNone( row )
        self.assertEqual( row['co_material'], 666 )
        self.assertTrue( row['outlet_okay'] )
        self.assertTrue( row['inlet_okay'] )
        self.assertFalse( row['structure_okay'] )

        row = {
                'co_material': 5547
        }

        # update
        self.update('manhole_quarantine', row, obj_id, 'qgep_import')
        
        # it should be updated in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertEqual( row['co_material'], 5547)

        # it shouldn't be anymore in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNone( row )


    # - problematic update with 1 old outlet and 1 new outlet and 0 old inlet and 1 new inlet
    #   -> updated structure
    #   -> updated reach for outlet
    #   -> still in quarantene
    #   - update inlet_okay true
    #     -> deleted in quarantene
    def test_update_with_unexpected_inlet(self):
        # obj_id from the test data
        obj_id = 'ch13p7mzMA000012'

        # change remark from 'Strasseneinlauf' to 'Strassenauslauf'
        # change co_material from 233 to 3015
        row = {
                'remark': 'Strassenauslauf',
                'co_material': 3015,
                'outlet_1_material': 5081,
                'outlet_1_dimension_mm': 160,
                'outlet_1_depth_m': 100,
                'inlet_3_material': 5081,
                'inlet_3_dimension_mm': 160,
                'inlet_3_depth_m': 100
        }

        # update
        self.update('vw_manhole', row, obj_id, 'qgep_import')

        # it should be in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertEqual( row['co_material'], 3015)
        self.assertEqual( row['remark'], 'Strassenauslauf')

        # it should be in the live table qgep_od.reach and qgep_od.reach_point
        cur = self.cursor()
        cur.execute("SELECT re.material, re.clear_height, rp.level, ws.co_level\
            FROM {schema}.reach re\
            LEFT JOIN {schema}.reach_point rp ON rp.obj_id = re.fk_reach_point_from\
            LEFT JOIN {schema}.wastewater_networkelement wn ON wn.obj_id = rp.fk_wastewater_networkelement\
            LEFT JOIN {schema}.vw_qgep_wastewater_structure ws ON ws.obj_id = wn.fk_wastewater_structure\
            WHERE ws.obj_id = '{obj_id}'".format(schema='qgep_od', obj_id=obj_id))
        row = cur.fetchone()
        self.assertIsNotNone( row )
        self.assertEqual( row['material'], 5081)
        self.assertEqual( row['clear_height'], 160)
        self.assertEqual( row['level'], decimal.Decimal('301.700'))

        # it should be still in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNotNone( row )

        row = {
                'inlet_okay': 'true'
        }

        # update
        self.update('manhole_quarantine', row, obj_id, 'qgep_import')

        # it shouldn't be anymore in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNone( row )


    # - problematic update with 1 old outlet and 0 new outlet and 0 old inlet and 0 new inlet
    #   -> updated structure
    #   -> still in quarantene
    #   - update outlet_okay true
    #     -> deleted in quarantene
    def test_update_with_unexpected_outlet(self):
        # obj_id from the test data
        obj_id = 'ch13p7mzMA000012'

        # change remark from 'Strasseneinlauf' to 'Strassenauslauf'
        # change co_material from 233 to 3015
        row = {
                'remark': 'Strassenauslauf',
                'co_material': 3015
        }

        # update
        self.update('vw_manhole', row, obj_id, 'qgep_import')

        # it should be in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertEqual( row['co_material'], 3015)
        self.assertEqual( row['remark'], 'Strassenauslauf')

        # it should be still in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNotNone( row )

        row = {
                'outlet_okay': 'true'
        }

        # update
        self.update('manhole_quarantine', row, obj_id, 'qgep_import')

        # it shouldn't be anymore in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNone( row )


    # - problematic update with 1 old outlet and 1 new outlet and 4 old inlet and 4 new inlet
    #   -> updated structure
    #   -> updated reach for outlet
    #   -> still in quarantene
    #   - update inlet_okay true
    #     -> deleted in quarantene
    def test_update_with_multiple_inlets(self):
        # obj_id from the test data
        obj_id = 'ch13p7mzMA005266'

        # change remark from 'E09' to 'E10'
        # change co_material from 3016 to 3015
        row = {
                'remark': 'E10',
                'co_material': 3015,
                'co_level': 500,
                'outlet_1_material': 5081,
                'outlet_1_dimension_mm': 160,
                'outlet_1_depth_m': 100,
                'inlet_3_material': 5081,
                'inlet_3_dimension_mm': 160,
                'inlet_3_depth_m': 100
        }

        # update
        self.update('vw_manhole', row, obj_id, 'qgep_import')

        # it should be in the view qgep_import.vw_manhole
        row = self.select( 'vw_manhole', obj_id, 'qgep_import')
        self.assertEqual( row['co_material'], 3015)
        self.assertEqual( row['remark'], 'E10')

        # it should be in the live table qgep_od.reach and qgep_od.reach_point
        cur = self.cursor()
        cur.execute("SELECT re.material, re.clear_height, rp.level, ws.co_level\
            FROM {schema}.reach re\
            LEFT JOIN {schema}.reach_point rp ON rp.obj_id = re.fk_reach_point_from\
            LEFT JOIN {schema}.wastewater_networkelement wn ON wn.obj_id = rp.fk_wastewater_networkelement\
            LEFT JOIN {schema}.vw_qgep_wastewater_structure ws ON ws.obj_id = wn.fk_wastewater_structure\
            WHERE ws.obj_id = '{obj_id}'".format(schema='qgep_od', obj_id=obj_id))
        row = cur.fetchone()
        self.assertIsNotNone( row )
        self.assertEqual( row['material'], 5081)
        self.assertEqual( row['clear_height'], 160)
        self.assertEqual( row['level'], decimal.Decimal('400'))

        # it should be still in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNotNone( row )

        row = {
                'inlet_okay': 'true'
        }

        # update
        self.update('manhole_quarantine', row, obj_id, 'qgep_import')

        # it shouldn't be anymore in the quarantine qgep_import.manhole_quarantine
        row = self.select( 'manhole_quarantine', obj_id, 'qgep_import')
        self.assertIsNone( row )


if __name__ == '__main__':
    unittest.main()