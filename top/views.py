import datetime

from django.http import HttpResponse
from django.views.generic.base import TemplateView
from django.utils import timezone
from django.db import connection
from django.http import Http404
from django.conf import settings

import pyodbc
import difflib
from . import models


def sp(x):
    return [x for x in x.splitlines() if x.strip()]


class IndexView(TemplateView):
    template_name = 'index.html'

    sql = '''
    select
        mst.id
        ,mst.name as name
        ,(select query from top_develop where master_id = mst.id and create_date < %s order by create_date desc limit 1) as dev_query
        ,(select query from top_staging where master_id = mst.id and create_date < %s order by create_date desc limit 1) as stg_query
        ,(select query from top_production where master_id = mst.id and create_date < %s order by create_date desc limit 1) as prd_query
        from top_schemamaster mst
        where
        mst.sysobject_type = %s
    '''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['now'] = timezone.now()
        now = kwargs.get('date', datetime.datetime.now())
        sysobject_type = kwargs.get('type', 'IF')
        procedure_list = []
        for row in models.SchemaMaster.objects.raw(IndexView.sql, [now, now, now, sysobject_type]):
            dev = row.dev_query if row.dev_query else ''
            stg = row.stg_query if row.stg_query else ''
            prd = row.prd_query if row.prd_query else ''
            row.d_ratio = difflib.SequenceMatcher(lambda x: x == " \t", sp(dev), sp(stg)).ratio()
            row.s_ratio = difflib.SequenceMatcher(lambda x: x == " \t", sp(stg), sp(prd)).ratio()
            procedure_list.append(row)
        context['procedure_list'] = procedure_list
        return context


class DetailView(TemplateView):
    template_name = 'detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = kwargs['name']
        sql = '''
        select
        mst.id
        ,mst.name as name
        ,(select query from top_develop where master_id = mst.id order by create_date desc limit 1) as dev_query
        ,(select query from top_staging where master_id = mst.id order by create_date desc limit 1) as stg_query
        ,(select query from top_production where master_id = mst.id order by create_date desc limit 1) as prd_query
        from top_schemamaster mst
        where
        mst.name = '{name}'
        '''.format(name=name)

        rows = models.SchemaMaster.objects.raw(sql)
        if not rows:
            raise Http404
        row = rows[0]
        dev = row.dev_query if row.dev_query else ''
        stg = row.stg_query if row.stg_query else ''
        prd = row.prd_query if row.prd_query else ''
        context['dev2stg'] = (
            difflib.HtmlDiff(tabsize=2, wrapcolumn=80, linejunk=lambda x: x == ' \t\n')
                .make_table(fromlines=sp(dev), tolines=sp(stg), fromdesc="DEVELOP", todesc="STAGING")
        )
        context['stg2prd'] = (
            difflib.HtmlDiff(tabsize=2, wrapcolumn=80, linejunk=lambda x: x == ' \t\n')
                .make_table(fromlines=sp(stg), tolines=sp(prd), fromdesc="STAGING", todesc="PRODUCTION")
        )
        return context


def connection(server, user, password, db):
    return pyodbc.connect("DRIVER={ODBC Driver 17 for SQL Server};SERVER=" + server + ";uid=" + user + \
                 ";pwd=" + password + ";DATABASE=" + db)


sysobjects_types = ','.join(["'" + x[0] + "'" for x in models.SYS_OBJECT_TYPE])

schema_sql = f'''select sysobjects.name as name
      ,sys.sql_modules.definition as query
      ,sysobjects.type as sysobject_type
      ,sysobjects.crdate as create_date
FROM   sys.sql_modules
LEFT OUTER JOIN sysobjects
ON  sysobjects.id = sys.sql_modules.object_id
WHERE sysobjects.type in ({sysobjects_types})
ORDER BY sysobjects.name'''


def sync(request):
    databases = (
        (models.Develop, settings.DEVELOP_CONNECTION),
        (models.Staging, settings.STAGING_CONNECTION),
        (models.Production, settings.PRODUCTION_CONNECTION),
    )
    for env, dns in databases:
        with pyodbc.connect(dns) as con:
            with con.cursor() as cur:
                cur.execute(schema_sql)
                desc = cur.description
                elems = []
                for row in [dict(zip([col[0] for col in desc], row)) for row in cur.fetchall()]:
                    master, created = models.SchemaMaster.objects.get_or_create(
                        name=row['name'],
                        sysobject_type=row['sysobject_type']
                    )
                    q = env.objects.filter(
                        master=master,
                        create_date=row['create_date']
                    ).exists()
                    if q:
                        continue

                    elems.append(env(
                        master=master,                        
                        create_date=row['create_date'],
                        query=row['query']
                    ))
                env.objects.bulk_create(elems)
    return HttpResponse('sync')
