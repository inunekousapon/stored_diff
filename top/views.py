import datetime
import hashlib
import difflib

from django.http import HttpResponse
from django.views.generic.base import TemplateView
from django.utils import timezone
from django.db import connection
from django.http import Http404
from django.conf import settings
from django.shortcuts import redirect

import pyodbc
from . import models
from pygments import highlight
from pygments.lexers.sql import SqlLexer
from pygments.formatters import HtmlFormatter

from .createsql import TableList, TableSchemas


def sp(x):
    return [x for x in x.splitlines() if x.strip()]


class IndexView(TemplateView):
    template_name = "index.html"

    sql = """
    select
        mst.id
        ,mst.name as name
        ,(select query from top_develop where master_id = mst.id and create_date < %s order by create_date desc limit 1) as dev_query
        ,(select count(1) from top_develop where master_id = mst.id) as dev_count
        ,(select query from top_staging where master_id = mst.id and create_date < %s order by create_date desc limit 1) as stg_query
        ,(select count(1) from top_staging where master_id = mst.id) as stg_count
        ,(select query from top_production where master_id = mst.id and create_date < %s order by create_date desc limit 1) as prd_query
        ,(select count(1) from top_production where master_id = mst.id) as prd_count
        from top_schemamaster mst
        where
        mst.sysobject_type = %s
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["now"] = timezone.now()
        now = self.request.GET.getlist("date", [datetime.datetime.now()])[0]
        sysobject_type = self.request.GET.getlist("type", ["IF"])[0]
        keyword = self.request.GET.get("keyword", None)
        procedure_list = []
        for row in models.SchemaMaster.objects.raw(
            IndexView.sql, [now, now, now, sysobject_type]
        ):
            dev = row.dev_query if row.dev_query else ""
            stg = row.stg_query if row.stg_query else ""
            prd = row.prd_query if row.prd_query else ""
            # キーワード検索するとき、クエリに一つも含まれなければ無視する
            if keyword:
                if ((keyword not in dev) and (keyword not in stg) and (keyword not in prd)):
                    continue
            row.d_ratio = difflib.SequenceMatcher(
                lambda x: x == " \t", sp(dev), sp(stg)
            ).ratio()
            row.s_ratio = difflib.SequenceMatcher(
                lambda x: x == " \t", sp(stg), sp(prd)
            ).ratio()
            procedure_list.append(row)
        context["procedure_list"] = procedure_list
        context["sysobject_type"] = sysobject_type
        context["keyword"] = keyword if keyword else ""
        return context


class DetailView(TemplateView):
    template_name = "detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = kwargs["name"]
        sql = """
        select
        mst.id
        ,mst.name as name
        ,(select query from top_develop where master_id = mst.id order by create_date desc limit 1) as dev_query
        ,(select query from top_staging where master_id = mst.id order by create_date desc limit 1) as stg_query
        ,(select query from top_production where master_id = mst.id order by create_date desc limit 1) as prd_query
        from top_schemamaster mst
        where
        mst.name = '{name}'
        """.format(
            name=name
        )

        rows = models.SchemaMaster.objects.raw(sql)
        if not rows:
            raise Http404
        row = rows[0]
        dev = row.dev_query if row.dev_query else ""
        stg = row.stg_query if row.stg_query else ""
        prd = row.prd_query if row.prd_query else ""
        context["dev2stg"] = difflib.HtmlDiff(
            tabsize=2, wrapcolumn=80, linejunk=lambda x: x == " \t\n"
        ).make_table(
            fromlines=sp(dev), tolines=sp(stg), fromdesc="DEVELOP", todesc="STAGING"
        )
        context["stg2prd"] = difflib.HtmlDiff(
            tabsize=2, wrapcolumn=80, linejunk=lambda x: x == " \t\n"
        ).make_table(
            fromlines=sp(stg), tolines=sp(prd), fromdesc="STAGING", todesc="PRODUCTION"
        )
        return context


class RawView(TemplateView):
    template_name = "raw.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = kwargs["name"]
        target = kwargs.get("target", "dev")

        if target == "dev":
            db_target = "top_develop"
        elif target == "stg":
            db_target = "top_staging"
        elif target == "prd":
            db_target = "top_production"
        else:
            raise Http404

        sql = """
        select
        mst.id
        ,mst.name as name
        ,(select query from {} where master_id = mst.id order by create_date desc limit 1) as query
        from top_schemamaster mst
        where
        mst.name = %s
        """.format(
            db_target
        )

        rows = [x for x in models.SchemaMaster.objects.raw(sql, [name])]
        if not rows:
            raise Http404

        context["code"] = highlight(
            rows[0].query,
            SqlLexer(),
            HtmlFormatter(full=True, linenos=True, title=name, wrapcode=True),
        )
        return context


class RevisionView(TemplateView):
    template_name = "rev.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        name = kwargs["name"]
        target = kwargs.get("target", "dev")
        revision = kwargs.get("rev", 0)
        if target == "dev":
            db_target = "top_develop"
        elif target == "stg":
            db_target = "top_staging"
        elif target == "prd":
            db_target = "top_production"
        else:
            raise Http404
        sql = """
        select
        mst.id
        ,mst.name as name
        ,t.query as query
        ,t.create_date as create_date
        from top_schemamaster mst
        inner join {} t on t.master_id = mst.id
        where
        mst.name = %s
        order by t.create_date desc
        """.format(
            db_target
        )

        rows = [x for x in models.SchemaMaster.objects.raw(sql, [name])]
        if not rows:
            raise Http404
        if revision + 1 == len(rows):
            cur = ""
            cur_date = ""
            old = rows[revision].query
            old_date = rows[revision].create_date
        elif revision + 1 > len(rows):
            raise Http404
        else:
            cur = rows[revision].query
            cur_date = rows[revision].create_date
            old = rows[revision + 1].query
            old_date = rows[revision + 1].create_date
        context["diff"] = difflib.HtmlDiff(
            tabsize=2, wrapcolumn=80, linejunk=lambda x: x == " \t\n"
        ).make_table(
            fromlines=sp(old), tolines=sp(cur), fromdesc=old_date, todesc=cur_date
        )
        return context


def connection(server, user, password, db):
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};SERVER="
        + server
        + ";uid="
        + user
        + ";pwd="
        + password
        + ";DATABASE="
        + db
    )


schema_sql = """select sysobjects.name as name
      ,sys.sql_modules.definition as query
      ,sysobjects.type as sysobject_type
      ,sysobjects.crdate as create_date
FROM   sys.sql_modules
LEFT OUTER JOIN sysobjects
ON  sysobjects.id = sys.sql_modules.object_id
WHERE sysobjects.type in ('IF', 'P', 'V')
ORDER BY sysobjects.name"""


def sync(request):
    databases = (
        (models.Develop, settings.DEVELOP_CONNECTION),
        (models.Staging, settings.STAGING_CONNECTION),
        (models.Production, settings.PRODUCTION_CONNECTION),
    )
    now = datetime.datetime.now()
    for env, dns in databases:
        with pyodbc.connect(dns) as con:
            with con.cursor() as cur:
                cur.execute(schema_sql)
                desc = cur.description
                elems = []
                for row in [
                    dict(zip([col[0] for col in desc], row)) for row in cur.fetchall()
                ]:
                    master, created = models.SchemaMaster.objects.update_or_create(
                        name=row["name"],
                        sysobject_type=row["sysobject_type"].strip(),  # 空白文字返るのふざけるな
                    )
                    query = row["query"] if row is not None else ""
                    hexdigest = hashlib.sha224(query.encode()).hexdigest()
                    q = env.objects.filter(master=master, shahex=hexdigest).exists()
                    if q:
                        continue

                    elems.append(
                        env(
                            master=master,
                            create_date=now,
                            query=query,
                            shahex=hexdigest,
                        )
                    )
                #tablelist = TableList(cursor=cur)
                #tablescheme = TableSchemas(cursor=cur)
                #usertables = tablelist.makedata()
                #for row in tablescheme.makedata(usertables):
                #    master, created = models.SchemaMaster.objects.update_or_create(
                #        name=row[0], sysobject_type="U"
                #    )
                #    hexdigest = hashlib.sha224(row[1].encode()).hexdigest()
                #    q = env.objects.filter(master=master, shahex=hexdigest).exists()
                #    if q:
                #        continue
                #    elems.append(
                #        env(
                #            master=master,
                #            create_date=now,
                #            query=row[1],
                #            shahex=hexdigest,
                #        )
                #    )
                env.objects.bulk_create(elems)

    return redirect("/")
