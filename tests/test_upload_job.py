# -*- coding: utf-8 -*-
from __future__ import absolute_import
from mock import patch, Mock
import io
from flask import current_app
from tests import BaseTestCase
from kepler.jobs import (create_job, UploadJob, ShapefileUploadJob,
                         GeoTiffUploadJob,)
from kepler.extensions import db
from kepler.models import Job
from kepler.exceptions import UnsupportedFormat

class JobTestCase(BaseTestCase):
    def setUp(self):
        super(JobTestCase, self).setUp()
        self.data = Mock()
        self.data.filename = u'TestFile'
        self.data.mimetype = 'application/zip'


class JobFactoryTestCase(JobTestCase):
    def testCreateJobCreatesJob(self):
        create_job(self.data)
        self.assertEqual(Job.query.count(), 1)

    def testJobIsCreatedWithPendingStatus(self):
        create_job(self.data)
        job = Job.query.first()
        self.assertEqual(job.status, 'PENDING')

    def testCreateJobReturnsJob(self):
        job = create_job(self.data)
        self.assertIsInstance(job, UploadJob)

    def testCreateJobCreatesShapefileJobFromMimetype(self):
        job = create_job(self.data)
        self.assertIsInstance(job, ShapefileUploadJob)

    def testCreateJobCreatesGeoTiffJobFromMimetype(self):
        self.data.mimetype = 'image/tiff'
        job = create_job(self.data)
        self.assertIsInstance(job, GeoTiffUploadJob)

    def testCreateJobSetsFailedStatusOnError(self):
        with patch('kepler.jobs.ShapefileUploadJob') as mock:
            mock.side_effect = Exception
            try:
                create_job(self.data)
            except:
                pass
            self.assertEqual(Job.query.first().status, 'FAILED')

    def testCreateJobReRaisesExceptions(self):
        with patch('kepler.jobs.ShapefileUploadJob') as mock:
            mock.side_effect = AttributeError()
            with self.assertRaises(AttributeError):
                create_job(self.data)

    def testCreateJobRaisesUnsupportedFormat(self):
        self.data.mimetype = 'application/example'
        with self.assertRaises(UnsupportedFormat):
            create_job(self.data)


class UploadJobTestCase(JobTestCase):
    def testFailSetsFailedStatus(self):
        job = Job(name=None, status=u'PENDING')
        db.session.add(job)
        db.session.commit()
        uploadjob = UploadJob(job, data=None)
        uploadjob.fail()
        self.assertEqual(Job.query.first().status, 'FAILED')

    def testCompleteSetsCompletedStatus(self):
        job = Job(name=None, status=u'PENDING')
        db.session.add(job)
        db.session.commit()
        uploadjob = UploadJob(job, data=None)
        uploadjob.complete()
        self.assertEqual(Job.query.first().status, 'COMPLETED')

    def testRunMethodRaisesNotImplementedError(self):
        with self.assertRaises(NotImplementedError):
            job = UploadJob(job=None, data=None)
            job.run()


class ShapefileUploadJobTestCase(JobTestCase):
    @patch('requests.put')
    def testRunUploadsShapefileToGeoserver(self, mock):
        job = ShapefileUploadJob(job=Job(), data=self.data)
        job.run()
        mock.assert_called_with(
            'http://example.com/geoserver/rest/workspaces/mit/datastores/data/file.shp',
            data=self.data, headers={'Content-type': 'application/zip'})

    def testCreateRecordReturnsMetadataRecord(self):
        metadata = io.open('tests/data/shapefile/fgdc.xml', encoding='utf-8')
        job = ShapefileUploadJob(job=Job(), data=self.data)
        record = job.create_record(metadata)
        self.assertEqual(record.dc_title_s,
                         'Bermuda (Geographic Feature Names, 2003)')
        self.assertEqual(record.dc_rights_s, 'Public')
        self.assertEqual(record.dct_provenance_s, 'MIT')

    def testCreateRecordAddsLayerId(self):
        metadata = io.open('tests/data/shapefile/fgdc.xml', encoding='utf-8')
        job = ShapefileUploadJob(job=Job(), data=self.data)
        record = job.create_record(metadata)
        self.assertEqual(record.layer_id_s, 'mit:TestFile')
