from django.test import SimpleTestCase, override_settings

from weni.eda.django.connection_params import AMQConnectionParamsFactory


@override_settings(
    USE_EDA=True,
    AMQ_BROKER_HOST="broker.example.com",
    AMQ_BROKER_PORT=5671,
    AMQ_BROKER_USER="amq-user",
    AMQ_BROKER_PASSWORD="amq-pass",
    AMQ_VIRTUAL_HOST="/commerce",
)
class AMQConnectionParamsFactoryTestCase(SimpleTestCase):
    def test_builds_connection_params_from_settings(self):
        params = AMQConnectionParamsFactory.get_params()

        self.assertEqual(params.host, "broker.example.com")
        self.assertEqual(params.port, 5671)
        self.assertEqual(params.userid, "amq-user")
        self.assertEqual(params.password, "amq-pass")
        self.assertEqual(params.virtual_host, "/commerce")
        self.assertTrue(params.ssl)

    def test_embeds_port_in_host_for_pyamqp(self):
        params = AMQConnectionParamsFactory.get_params()

        self.assertEqual(params.value["host"], "broker.example.com:5671")

    def test_does_not_double_embed_port_in_host(self):
        params = AMQConnectionParamsFactory.get_params()

        self.assertNotIn(":5671:5671", params.value["host"])

    @override_settings(AMQ_BROKER_HOST="amazonmq.local", AMQ_BROKER_PORT=5672)
    def test_supports_custom_port(self):
        params = AMQConnectionParamsFactory.get_params()

        self.assertEqual(params.value["host"], "amazonmq.local:5672")
