#!/usr/bin/env python
"""
Script para imprimir o conteúdo que seria enviado no publisher na criação de projetos.

Execute com: 
  python manage.py shell < weni-scripts/print_publisher_content.py
Ou:
  python weni-scripts/print_publisher_content.py
"""

import os
import sys
import json

# Setup Django se executado como script standalone
if __name__ == "__main__":
    import django
    # Adiciona o diretório do projeto ao path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.insert(0, project_root)
    os.chdir(project_root)
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "connect.settings")
    django.setup()

# Importar modelos (funciona tanto no shell quanto como script standalone)
from connect.common.models import Project, Organization


def build_publisher_message_body(project, brain_on=False, extra_fields=None):
    """
    Constrói o message_body que seria enviado no publisher na criação de projetos.
    Replica a lógica do método publish_create_project_message do ProjectSerializer.
    """
    # Buscar autorizações da organização
    authorizations = []
    for authorization in project.organization.authorizations.all():
        if authorization.can_contribute:
            authorizations.append(
                {"user_email": authorization.user.email, "role": authorization.role}
            )
    
    # Construir message_body
    message_body = {
        "uuid": str(project.uuid),
        "name": project.name,
        "is_template": project.is_template,
        "user_email": project.created_by.email if project.created_by else None,
        "date_format": project.date_format,
        "template_type_uuid": (
            str(project.project_template_type.uuid)
            if project.project_template_type
            else None
        ),
        "timezone": str(project.timezone),
        "organization_id": project.organization.inteligence_organization,
        "extra_fields": extra_fields if project.is_template else {},
        "authorizations": authorizations,
        "description": project.description,
        "organization_uuid": str(project.organization.uuid),
        "brain_on": brain_on,
        "project_type": project.project_type.value,
        "vtex_account": project.vtex_account,
    }
    
    return message_body


def print_project_publisher_content(project_uuid, brain_on=False, extra_fields=None):
    """Imprime o conteúdo que seria enviado no publisher para um projeto."""
    try:
        project = Project.objects.get(uuid=project_uuid)
        
        print(f"\n{'='*80}")
        print(f"PROJETO: {project.name}")
        print(f"UUID: {project.uuid}")
        print(f"Organização: {project.organization.name} ({project.organization.uuid})")
        print(f"{'='*80}\n")
        
        message_body = build_publisher_message_body(project, brain_on, extra_fields)
        
        print("CONTEÚDO QUE SERIA ENVIADO NO PUBLISHER:")
        print(f"Exchange: projects.topic")
        print(f"Routing Key: (vazio)")
        print(f"\nMessage Body (JSON formatado):")
        print(json.dumps(message_body, indent=2, ensure_ascii=False))
        print(f"\n{'-'*80}\n")
        
        return message_body
        
    except Project.DoesNotExist:
        print(f"❌ Erro: Projeto com UUID {project_uuid} não encontrado")
        return None
    except Exception as e:
        print(f"❌ Erro ao processar projeto: {e}")
        import traceback
        traceback.print_exc()
        return None


# UUIDs fornecidos
ORG_UUID = "69fce360-7806-45b6-8b1b-49f918a1c448"
PROJECT_UUIDS = [
    "db2fd124-16b7-4ee0-a361-0e38c9609967",
    "1a197c22-0513-47e2-aea5-0b0c4841b3aa"
]

if __name__ == "__main__":
    print("\n" + "="*80)
    print("SCRIPT: Print Publisher Content para Criação de Projetos")
    print("="*80)
    
    # Verificar organização
    try:
        org = Organization.objects.get(uuid=ORG_UUID)
        print(f"\n✓ Organização encontrada: {org.name} ({org.uuid})")
    except Organization.DoesNotExist:
        print(f"\n⚠ Aviso: Organização {ORG_UUID} não encontrada")
    except Exception as e:
        print(f"\n⚠ Erro ao buscar organização: {e}")
    
    # Processar cada projeto
    print(f"\nProcessando {len(PROJECT_UUIDS)} projeto(s)...\n")
    
    for project_uuid in PROJECT_UUIDS:
        print_project_publisher_content(project_uuid)
    
    print("\n" + "="*80)
    print("Script concluído!")
    print("="*80 + "\n")

