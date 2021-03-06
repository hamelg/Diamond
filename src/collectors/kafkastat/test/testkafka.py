#!/usr/bin/python
# coding=utf-8
###############################################################################
import urllib2

try:
    from xml.etree import ElementTree
except ImportError:
    ElementTree = None

from test import CollectorTestCase
from test import get_collector_config
from test import run_only
from test import unittest
from mock import patch

from diamond.collector import Collector
from kafkastat import KafkaCollector

##########


def run_only_if_ElementTree_is_available(func):
    try:
        from xml.etree import ElementTree
    except ImportError:
        ElementTree = None
    pred = lambda: ElementTree is not None
    return run_only(func, pred)


class TestKafkaCollector(CollectorTestCase):

    def setUp(self):
        config = get_collector_config('KafkaCollector', {
            'interval': 10
        })

        self.collector = KafkaCollector(config, None)

    def _get_xml_fixture(self, name):
        fixture = self.getFixture(name)

        return ElementTree.fromstring(fixture.getvalue())

    def test_import(self):
        self.assertTrue(KafkaCollector)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get(self, urlopen_mock):
        urlopen_mock.return_value = self.getFixture('empty.xml')

        result = self.collector._get('/path')
        result_string = ElementTree.tostring(result)

        self.assertEqual(result_string, '<Server />')

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get_httperror(self, urlopen_mock):
        urlopen_mock.side_effect = urllib2.URLError('BOOM')

        result = self.collector._get('/path')

        self.assertFalse(result)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    def test_get_bad_xml(self, urlopen_mock):
        urlopen_mock.return_value = self.getFixture('bad.xml')

        result = self.collector._get('/path')

        self.assertFalse(result)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_get_mbeans(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('serverbydomain.xml')

        expected_names = set([
            'kafka:type=kafka.BrokerAllTopicStat',
            'kafka:type=kafka.BrokerTopicStat.mytopic',
            'kafka:type=kafka.LogFlushStats',
            'kafka:type=kafka.SocketServerStats',
            'kafka:type=kafka.logs.mytopic-0',
            'kafka:type=kafka.logs.mytopic-1',
            'kafka:type=kafka.Log4jController',
        ])

        found_beans = self.collector.get_mbeans('*')

        self.assertEqual(found_beans, expected_names)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_get_mbeans_get_fail(self, get_mock):
        get_mock.return_value = None

        found_beans = self.collector.get_mbeans('*')

        self.assertEqual(found_beans, None)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('mbean.xml')

        expected_metrics = {
            'kafka.logs.mytopic-1.CurrentOffset': long('213500615'),
            'kafka.logs.mytopic-1.NumAppendedMessages': long('224634137'),
            'kafka.logs.mytopic-1.NumberOfSegments': int('94'),
            'kafka.logs.mytopic-1.Size': long('50143615339'),
        }

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-1')

        self.assertEqual(metrics, expected_metrics)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean2(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('mbean2.xml')

        expected_metrics = {
            'Log.LogStartOffset.topic.packetbeat.partition.0.Value':
            long('2774314'),
        }

        metrics = self.collector.query_mbean(
            'kafka.log:type=Log,name=LogStartOffset,'
            'topic=packetbeat,partition=0')

        self.assertEqual(metrics, expected_metrics)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean_with_prefix(self, get_mock):
        get_mock.return_value = self._get_xml_fixture('mbean.xml')

        expected_metrics = {
            'some.prefix.CurrentOffset': long('213500615'),
            'some.prefix.NumAppendedMessages': long('224634137'),
            'some.prefix.NumberOfSegments': int('94'),
            'some.prefix.Size': long('50143615339'),
        }

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-0',
                                             'some.prefix')

        self.assertEqual(metrics, expected_metrics)

    @run_only_if_ElementTree_is_available
    @patch.object(KafkaCollector, '_get')
    def test_query_mbean_fail(self, get_mock):
        get_mock.return_value = None

        metrics = self.collector.query_mbean('kafka:type=kafka.logs.mytopic-0')

        self.assertEqual(metrics, None)

    @run_only_if_ElementTree_is_available
    @patch('urllib2.urlopen')
    @patch.object(Collector, 'publish')
    def test(self, publish_mock, urlopen_mock):
        urlopen_mock.side_effect = [
            self.getFixture('serverbydomain_logs_only.xml'),
            self.getFixture('serverbydomain_gc.xml'),
            self.getFixture('serverbydomain_threading.xml'),
            self.getFixture('gc_scavenge.xml'),
            self.getFixture('gc_marksweep.xml'),
            self.getFixture('mbean.xml'),
            self.getFixture('threading.xml'),
        ]
        self.collector.collect()

        expected_metrics = {
            'kafka.logs.mytopic-1.CurrentOffset': 213500615,
            'kafka.logs.mytopic-1.NumAppendedMessages': 224634137,
            'kafka.logs.mytopic-1.NumberOfSegments': 94,
            'kafka.logs.mytopic-1.Size': 50143615339,
            'Threading.CurrentThreadCpuTime': 0,
            'Threading.CurrentThreadUserTime': 0,
            'Threading.DaemonThreadCount': 58,
            'Threading.PeakThreadCount': 90,
            'Threading.ThreadCount': 89,
            'Threading.TotalStartedThreadCount': 228,
            'GarbageCollector.PSScavenge.CollectionCount': 37577,
            'GarbageCollector.PSScavenge.CollectionTime': 112293,
            'GarbageCollector.PSMarkSweep.CollectionCount': 2,
            'GarbageCollector.PSMarkSweep.CollectionTime': 160,
        }

        self.assertPublishedMany(publish_mock, expected_metrics)

###############################################################################
if __name__ == "__main__":
    unittest.main()
