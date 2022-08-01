import pendulum
from connect.common.models import Project
from connect.billing.models import SyncManagerTask, Contact, Message, Channel
from django.test import TestCase
from .contact_factory import get_active_contacts


class RetroactiveContactsTestCase(TestCase):
    def setUp(self) -> None:

        self.after = pendulum.now().start_of("day")
        self.before = self.after.add(hours=3)

        self.last_retroactive_sync = SyncManagerTask.objects.create(
                task_type="retroactive_sync",
                status=True,
                before=self.before,
                after=self.after,
                started_at=pendulum.now().subtract(minutes=5),
                finished_at=pendulum.now()
            )


    def test_sync_contacts_retroactive(self):

        last_retroactive_sync = (
            SyncManagerTask.objects.filter(
                task_type="retroactive_sync",
                status=True,
            )
            .order_by("before")
            .last()
        )

        if last_retroactive_sync:
            after = pendulum.instance(last_retroactive_sync.before)
            before = after.add(hours=3)

        manager = SyncManagerTask.objects.create(
            task_type="retroactive_sync",
            started_at=pendulum.now(),
            before=before,
            after=after,
        )
        try:
            # flow_instance = utils.get_grpc_types().get("flow")
            for project in Project.objects.exclude(flow_id=None):
                active_contacts = get_active_contacts(
                        str(project.flow_organization),
                        before.strftime("%Y-%m-%d %H:%M"),
                        after.strftime("%Y-%m-%d %H:%M"),
                    )
                print("active: ", active_contacts)
                for contact in active_contacts:
                    contact = Contact.objects.create(
                        contact_flow_uuid=contact.uuid,
                        name=contact.name,
                        last_seen_on=pendulum.from_timestamp(
                            contact.msg.sent_on.seconds.real
                        ),
                    )
                    message = Message.objects.create(
                        contact=contact,
                        text=contact.msg.text,
                        created_on=pendulum.from_timestamp(
                            contact.msg.sent_on.seconds.real
                        ),
                        direction=contact.msg.direction,
                        message_flow_uuid=contact.msg.uuid,
                    )
                    channel = Channel.create(
                        channel_type=message.channel_type,
                        channel_flow_id=contact.channel.uuid,
                        project=project,
                    )
                    contact.update_channel(channel)
                    print(contact)
            manager.finished_at = pendulum.now()
            manager.status = True
            manager.save(update_fields=["finished_at", "status"])
        except Exception as error:
            print(error)
            manager.finished_at = pendulum.now()
            manager.fail_message.create(message=str(error))
            manager.status = False
            manager.save(update_fields=["finished_at", "status"])

        
        self.assertEquals(manager.before, before)
        self.assertTrue(manager.status)








# from connect.billing.tests.test_retroactive import ContactDetail;import pendulum
# before = pendulum.now();after = before.subtract(hours=15)
# c = ContactDetail(before, after)

# ActiveContactDetail, Msg, Channel
# {
#     string uuid = 1;
#     string text = 2;
#     google.protobuf.Timestamp sent_on = 3;
#     Direction direction = 4;
# }

# message Channel {
#     string uuid = 1;
#     string name = 2;
# }

# {
#     string uuid = 1;
#     string name = 2;
#     Msg msg = 3;
#     Channel channel = 4;
# }


# , uuid: "ed25e9ff-df5d-49d0-9a7e-204c2701109e"
# name: "ANTONIO JOSE OLIVEIRA DE ANDRADE"
# msg {
#   uuid: "02ccaa5d-febc-47dd-b998-bf4ee8ada0bd"
#   text: "Por favor, antes de desconectar, avalie esse servi\303\247o. \nD\303\252 uma nota de 1 a 10, sendo:\n\n1.Ruim \360\237\230\224 >>> 10. Muito bom! \360\237\244\251"
#   sent_on {
#     seconds: 1656635233
#     nanos: 269115000
#   }
#   direction: OUTPUT
# }
# channel {
#   uuid: "3e0e1f0d-7418-43c2-9062-c3d72983891b"
#   name: "Assistente Virtual Sefaz - PE"
# }
# , uuid: "43825189-80d1-4a56-8775-d673b1f4b38f"
# name: "Irene Caroline da Silva Gomes"
# msg {
#   uuid: "7d9773a9-13e8-45d6-bc75-6aedbd296497"
#   text: "se tiver manda o n\303\272mero do codigo de barra (chave)"
#   sent_on {
#     seconds: 1656634670
#     nanos: 711997000
#   }
#   direction: OUTPUT
# }
# channel {
#   uuid: "83a77846-cc67-4f7e-8b37-5fddc4b6329e"
#   name: "Telegram - Sefaz/PE- Atendimento Online ao Contribuinte"
# }
# , uuid: "7f0eb682-816c-4ab3-a043-6cfac0f87ebb"
# msg {
#   uuid: "19d909a8-31d9-4986-bb5b-c9af7cf21592"
#   text: "Enviado pela ARe"
#   sent_on {
#     seconds: 1656635330
#   }
# }
# channel {
#   uuid: "83a77846-cc67-4f7e-8b37-5fddc4b6329e"
#   name: "Telegram - Sefaz/PE- Atendimento Online ao Contribuinte"
# }
# , uuid: "b5f47c86-6d8c-451e-bd59-7d05d74f328d"
# name: "Andre cavalcanti"
# msg {
#   uuid: "4fcebcdb-46ed-4d14-ad01-dfb6537bec94"
#   text: "Caso ainda tenha d\303\272vidas, entre em contato com nossos canais de atendimento:\n\n\360\237\222\254(81) 984941555 - Whatsapp\n\n\360\237\222\254@pe_sefaz_bot - Telegram\n\n\360\237\222\254 www.sefaz.pe.gov.br  - Chat\n\nOu ligue para o Telesefaz, das 8:00 \303\240s 18:00, atrav\303\251s dos n\303\272meros:\n\n\360\237\223\236 08002851244: para liga\303\247\303\265es feitas em Pernambuco atrav\303\251s de telefone fixo; ou\n\n\360\237\223\236 (81) 3183 6401: para as demais liga\303\247\303\265es (celular, outros Estados, etc). \n\nSecretaria de Fazenda \nGoverno do Estado Pernambuco"
#   sent_on {
#     seconds: 1656633707
#     nanos: 517115000
#   }
#   direction: OUTPUT
# }
# channel {
#   uuid: "83a77846-cc67-4f7e-8b37-5fddc4b6329e"
#   name: "Telegram - Sefaz/PE- Atendimento Online ao Contribuinte"
# }
# , uuid: "456560b5-d03b-40d0-a7f5-8c425495f1b2"
# msg {
#   uufrom weni.protobuf.flows import billing_pb2id: "25a51cb4-a3d9-4b0b-8652-43a955538127"
#   text: "Devido a inatividade, estamos encerrando o seu atendimento, tudo bem? \360\237\230\212\n\nMas n\303\243o se preocupe, voc\303\252 pode voltar a navegar aqui a qualquer momento. Basta dar um \"Oi!\" pra gente! \360\237\230\211"
#   sent_on {
#     seconds: 1656635103
#     nanos: 332626000
#   }
#   direction: OUTPUT
# }
# channel {
#   uuid: "3e0e1f0d-7418-43c2-9062-c3d72983891b"
#   name: "Assistente Virtual Sefaz - PE"
# }
# , uuid: "9d9d2a2f-b02c-44de-ba6f-df73e2e10f7d"
# name: "Elizabete Medeiros"
# msg {
#   uuid: "b3e4ff41-fd92-4714-89cd-9cab60c401c9"
#   text: "Devido a inatividade, estamos encerrando o seu atendimento, tudo bem? \360\237\230\212\n\nMas n\303\243o se preocupe, voc\303\252 pode voltar a navegar aqui a qualquer momento. Basta dar um \"Oi!\" pra gente! \360\237\230\211"
#   sent_on {
#     seconds: 1656634862
#     nanos: 489722000
#   }
#   direction: OUTPUT
# }
# channel {
#   uuid: "3e0e1f0d-7418-43c2-9062-c3d72983891b"
#   name: "Assistente Virtual Sefaz - PE"
# }
# ]
