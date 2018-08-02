from __future__ import unicode_literals

import traceback
from functools import partial, wraps
import json, csv
import datetime
from django.forms import formset_factory
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import CreateView, DeleteView
import simplejson
from anonymizer.lists import PROVIDER_PLUGINS
from forms import ConnectionConfigurationForm, Sqlite3ConnectionForm, MySQLConnectionForm, UserTableSelectionForm, \
    ColumnForm, validate_unique_across, PostgresConnectionForm
from models import ConnectionConfiguration, ConnectionAccessKey
from django.db import connections, transaction
from .forms import UploadCSVForm
from anonymizer.json_encoder import DefaultEncoder
from anonymizer_project import settings

# patch simplejson library to serialize datetimes
simplejson.JSONEncoder.default = lambda self, obj: (obj.isoformat() if isinstance(obj, datetime.datetime) else None)


# Create File Configuration

def createFileConfiguration(request):
    if request.method == 'POST':
        form = UploadCSVForm(request.POST, request.FILES)
        if form.is_valid():
            handle_uploaded_file(request.FILES['csv_file'], str(request.user.id))
            return redirect('/anonymizer/connection/parsefile')
    else:
        form = UploadCSVForm()
    return render(request, 'anonymizer/connection/createfile.html', {'form': form})


def handle_uploaded_file(f, userid):
    with open('private/' + userid, 'wb+') as destination:
        for chunk in f.chunks():
            destination.write(chunk)


def APIpreviewFile(request):
    data = []
    with open('private/' + str(request.user.id)) as fin:
        dialect = csv.Sniffer().sniff(fin.read(1024))
        fin.seek(0)
        for index, row in enumerate(csv.reader(fin, dialect=dialect)):
            if index > 5:
                break
            data.append(row)
    json_data = json.dumps(data, cls=DefaultEncoder)
    return HttpResponse(json_data)


def APIpreviewFileFull(request):
    data = []
    with open('private/' + str(request.user.id)) as fin:
        dialect = csv.Sniffer().sniff(fin.read(1024))
        fin.seek(0)
        for index, row in enumerate(csv.reader(fin, dialect=dialect)):
            data.append(row)
    json_data = json.dumps(data, cls=DefaultEncoder)
    return HttpResponse(json_data)


def parseFileConfiguration(request):
    if request.method == 'POST':
        # code here
        return redirect('anonymizer/connection/parsefile')
    else:
        data = {}
        for x in range(0, 3):
            data[x] = str(x)
    return render(request, 'anonymizer/connection/parsefile.html', {'data': data})


# Get the column data types of the CSV file
def _get_col_datatypes(fin, dialect):
    dr = csv.DictReader(fin, dialect=dialect)  # comma is default delimiter
    fieldTypes = {}
    for entry in dr:
        feildslLeft = [f for f in dr.fieldnames if f not in fieldTypes.keys()]
        if not feildslLeft: break  # We're done
        for field in feildslLeft:
            data = entry[field]

            # Need data to decide
            if len(data) == 0:
                continue

            if data.isdigit():
                fieldTypes[field] = "INTEGER"
            else:
                fieldTypes[field] = "TEXT"
                # TODO: Currently there's no support for DATE in sqllite

    if len(feildslLeft) > 0:
        raise Exception("Failed to find all the columns data types - Maybe some are empty?")

    return fieldTypes


# Remove non-appropriate characters
def escapingGenerator(f):
    for line in f:
        yield line.encode("ascii", "xmlcharrefreplace").decode("ascii")


def cleantext(s, TrimSpace=False):
    l = "".join(c for c in s if c not in "#!'")
    if TrimSpace == True:
        l = l.replace(" ", "")
    return l


def storeFileConfiguration(request):
    if request.method == 'POST':
        # Name of the connection
        connectionName = 'CSV_' + str(request.user.id) + datetime.datetime.now().strftime('%Y%m%d%H%M%S')
        # Store csv file in  Cache DB
        with open('private/' + str(request.user.id)) as fin:
            dialect = csv.Sniffer().sniff(fin.read(1024))
            fin.seek(0)
            # Get the datatypes
            dt = _get_col_datatypes(fin, dialect)

            fin.seek(0)

            reader = csv.DictReader(fin, dialect=dialect)

            # Keep the order of the columns name just as in the CSV
            fields = reader.fieldnames
            cols = []

            # Set field and type
            for f in fields:
                cols.append("%s %s" % (cleantext(f, TrimSpace=True), dt[f]))

            # Generate create table statement:
            querySQL = "CREATE TABLE IF NOT EXISTS " + connectionName + " (%s , PRIMARY KEY (cf))" % ",".join(cols)
            cursor = connections['anonymizerCache'].cursor()
            cursor.execute(querySQL)

            fin.seek(0)

            reader = csv.reader(escapingGenerator(fin), dialect=dialect)
            next(reader, None)  # skip the headers
            for row in reader:
                # Generate insert statement:
                querySQL = "INSERT INTO " + connectionName + " VALUES("
                values = ""
                for x in row:
                    values = values + "'" + cleantext(x) + "',"
                querySQL = querySQL + values[:-1] + ")"
                cursor.execute(querySQL)

        # Create a new connectionconfiguration
        config = ConnectionConfiguration.objects.create()
        config.connection_type = 'django.db.backends.psycopg2'
        config.name = connectionName.lower()
        config.users_table = connectionName.lower()
        config.info = '''
                "name": "''' + 'anonymizerCache' + '''",
                "user": "''' + settings.DATABASES['anonymizerCache']['USER'] + '''",
                "password": "''' + settings.DATABASES['anonymizerCache']['PASSWORD'] + '''",
                "host": "''' + settings.DATABASES['anonymizerCache']['HOST'] + '''",
                "port": "''' + settings.DATABASES['anonymizerCache']['PORT'] + '''"
            '''
        config.save()
        connection = config.get_connection()
        # Find table properties
        # detect primary key
        config.user_pk = connection.primary_key_of(config.users_table)

        # load default properties
        data_properties = connection.get_data_properties(config.users_table, from_related=True)
        few_properties = connection.get_data_properties(config.users_table)
        columns = few_properties[0]
        columns.insert(0, ('', '', ''))
        config.properties = config.get_default_properties(few_properties[0])
        config.foreign_keys = json.dumps(data_properties[1])

        # save changes
        config.save()

        return redirect('/anonymizer/connection/%d/select-columns/' % config.pk)


def home(request):
    params = {
        'configurations': ConnectionConfiguration.objects.all(),
    }

    return render(request, 'anonymizer/connection/home.html', params)


def risk(request):
    params = {
        'configurations': ConnectionConfiguration.objects.all(),
    }

    return render(request, 'anonymizer/connection/risk.html', params)


class ConnectionConfigurationCreateView(CreateView):
    """
    Allows the creation of the connection's configuration
    """
    model = ConnectionConfiguration
    form_class = ConnectionConfigurationForm
    template_name = 'anonymizer/connection/create.html'

    def get_success_url(self):
        return self.object.update_info_url()


create_configuration = ConnectionConfigurationCreateView.as_view()


def sqlite3_info(request, pk):
    """
    Update the info of a connection to an sqlite3 database
    """
    params = {}
    status = 200

    if request.method == 'GET':
        params['form'] = Sqlite3ConnectionForm()
    elif request.method == 'POST':
        form = Sqlite3ConnectionForm(request.POST, request.FILES)
        if form.is_valid():
            config = get_object_or_404(ConnectionConfiguration, pk=pk)
            config.info = '''
                  "name": "''' + form.cleaned_data['path'] + '''"
            '''
            config.save()

            return redirect('/anonymizer/connection/%d/suggest-user-table/' % config.pk)
        else:
            status = 400
            params['form'] = form

    return render(request, 'anonymizer/connection/update_info.html', params, status=status)


def mysql_info(request, pk):
    """
    Update the info of a connection to a mysql database
    """
    params = {}
    status = 200

    if request.method == 'GET':
        params['form'] = MySQLConnectionForm()
    elif request.method == 'POST':
        form = MySQLConnectionForm(request.POST)
        if form.is_valid():
            config = get_object_or_404(ConnectionConfiguration, pk=pk)
            data = form.cleaned_data
            config.info = '''
                "name": "''' + data['database'] + '''",
                "user": "''' + data['user'] + '''",
                "password": "''' + data['password'] + '''",
                "host": "''' + data['host'] + '''",
                "port": "''' + data['port'] + '''"
            '''
            config.save()

            return redirect('/anonymizer/connection/%d/suggest-user-table/' % config.pk)
        else:
            status = 400
            params['form'] = form

    return render(request, 'anonymizer/connection/update_info.html', params, status=status)


def postgres_info(request, pk):
    """
    Update the info of a connection to a postgres database
    """
    params = {}
    status = 200

    if request.method == 'GET':
        params['form'] = PostgresConnectionForm()
    elif request.method == 'POST':
        form = PostgresConnectionForm(request.POST)
        if form.is_valid():
            config = get_object_or_404(ConnectionConfiguration, pk=pk)
            data = form.cleaned_data
            config.info = '''
                "name": "''' + data['database'] + '''",
                "user": "''' + data['user'] + '''",
                "password": "''' + data['password'] + '''",
                "host": "''' + data['host'] + '''",
                "port": "''' + data['port'] + '''"
            '''
            config.save()

            return redirect('/anonymizer/connection/%d/suggest-user-table/' % config.pk)
        else:
            status = 400
            params['form'] = form

    return render(request, 'anonymizer/connection/update_info.html', params, status=status)


def suggest_users_table(request, pk):
    """
    Suggest to the user which table(s) probably contain the user info, let them select one
    """
    params = {}
    status = 200

    config = get_object_or_404(ConnectionConfiguration, pk=pk)
    connection = config.get_connection()

    if request.method == 'GET':
        params['form'] = UserTableSelectionForm(connection)
    elif request.method == 'POST':
        form = UserTableSelectionForm(connection, request.POST)
        if form.is_valid():
            config.users_table = form.cleaned_data['users_table']

            # detect primary key
            config.user_pk = connection.primary_key_of(config.users_table)

            # load default properties
            data_properties = connection.get_data_properties(config.users_table, from_related=True)
            few_properties = connection.get_data_properties(config.users_table)
            columns = few_properties[0]
            columns.insert(0, ('', '', ''))
            config.properties = config.get_default_properties(few_properties[0])
            config.foreign_keys = json.dumps(data_properties[1])

            # save changes
            config.save()

            return redirect('/anonymizer/connection/%d/select-columns/' % config.pk)
        else:
            status = 400
            params['form'] = form

    return render(request, 'anonymizer/connection/suggest_user_table.html', params, status=status)


def select_columns(request, pk):
    """
    Choose which columns to keep
    """
    params = {}
    status = 200

    config = get_object_or_404(ConnectionConfiguration, pk=pk)
    connection = config.get_connection()

    columns = connection.get_data_properties(config.users_table, from_related=True)[0]
    columns.insert(0, ('', '', ''))

    if not config.properties:
        # setup default properties
        config.properties = config.get_default_properties(columns)
        config.save()

    if request.method == 'GET':
        # gather suggestions
        initial = json.loads(config.properties)

        # resolve providers
        for initial_form in initial:
            for plugin in PROVIDER_PLUGINS:
                total_source = initial_form['source']
                if total_source.split('(')[0] != plugin['source']:
                    continue
                initial_form['source'] = total_source.split('(')[0]

                if 'args' in plugin:
                    plugin_params = total_source.split('(')[1][:-1]

                    for idx, option in enumerate(plugin_params.split(',')):
                        initial_form[plugin['source'] + '__param__' + plugin['args'][idx][0]] = option

        # create formset
        ColumnFormset = formset_factory(wraps(ColumnForm)(partial(ColumnForm, all_properties=columns)), extra=0)
        formset = ColumnFormset(initial=initial)

        params['formset'] = formset
    else:
        ColumnFormset = formset_factory(wraps(ColumnForm)(partial(ColumnForm, all_properties=columns)))
        formset = ColumnFormset(request.POST)

        if formset.is_valid():
            validate_unique_across(formset, ['name'])

        if formset.is_valid():
            properties = []
            for form in formset:
                p = {
                    'name': form.cleaned_data['name'],
                    'source': form.cleaned_data['source'],
                }

                if 'expose' in form.cleaned_data:
                    p['expose'] = bool(form.cleaned_data['expose'])
                else:
                    p['expose'] = False

                if 'options_auto' in form.cleaned_data:
                    p['options_auto'] = bool(form.cleaned_data['options_auto'])
                else:
                    p['options_auto'] = False

                if form.cleaned_data['aggregate']:
                    p['aggregate'] = form.cleaned_data['aggregate']

                if p['source'][0] != '^':  # don't try to join provider data
                    table_name = p['source'].split('.')[0]

                    # get type
                    if 'aggregate' in p and p['aggregate'] == 'avg':
                        p['type'] = 'FLOAT'
                    else:
                        for column in columns:
                            if p['source'] == column[2]:
                                p['type'] = column[1]
                                break

                    if table_name.lower() != config.users_table.lower():
                        if 'rel_to' in p:
                            rel_table = form.cleaned_data['rel_table']
                        else:
                            rel_table = config.users_table

                        p['rel_fk'] = connection.get_foreign_key_between(table_name, rel_table)
                        p['rel_to'] = connection.primary_key_of(rel_table)
                else:
                    # read plugin options
                    plugin_info = [plugin_info for plugin_info in PROVIDER_PLUGINS if
                                   plugin_info['source'] == p['source']][0]

                    # plugin return type
                    p['type'] = plugin_info['type']

                    # argument management
                    if 'args' in plugin_info:
                        plugin_options = plugin_info['args']
                        plugin_name = p['source']

                        option_values = []
                        for option in plugin_options:
                            key = plugin_name + '__param__' + option[0]
                            if key in form.cleaned_data:
                                option_values.append(form.cleaned_data[key])

                        p['source'] = '%s(%s)' % (plugin_name, ','.join(option_values))
                    else:
                        p['source'] = '%s()' % p['source']

                properties.append(p)

            # update configuration object
            config.properties = json.dumps(properties)
            config.save()

            return redirect('/anonymizer/')
        else:
            status = 400
            params['formset'] = formset

    return render(request, 'anonymizer/connection/select_columns.html', params, status=status)


def set_active(request, pk):
    """
    Activates a configuration
    """
    if request.method == 'POST':
        target = get_object_or_404(ConnectionConfiguration, pk=pk)

        target.is_active = True
        target.save()

        return redirect('/anonymizer/')
    else:
        return HttpResponse('Only POST method allowed', status=400)


def set_inactive(request, pk):
    """
    Dectivates a configuration
    """
    if request.method == 'POST':
        target = get_object_or_404(ConnectionConfiguration, pk=pk)

        target.is_active = False
        target.save()

        return redirect('/anonymizer/')
    else:
        return HttpResponse('Only POST method allowed', status=400)


def parse_filters(q):
    try:
        f_end = q.index('[')
    except ValueError:
        f_end = -1

    if f_end > 0:
        spl = q[f_end + 1:-1].split(':')
        if spl[0]:
            start = int(spl[0])
        else:
            start = None
        if len(spl) > 1:
            end = int(spl[1])
        else:
            end = None

        f_end -= 1
    else:
        start = None
        end = None

    return f_end, start, end


def query_connection(request, pk):
    """
    Execute a query against a connection
    """
    status = 200
    print('hello')
    config = get_object_or_404(ConnectionConfiguration, pk=pk)
    user_manager = config.get_user_manager(token=config.pk)

    if request.method != 'GET':
        return HttpResponse('Only GET requests are allowed', status=400)

    q = request.GET['q']
    result = ''

    if q:
        try:
            if q.startswith('all()'):
                _, start, end = parse_filters(q)

                result = user_manager.all(start=start, end=end)
            elif q.startswith('filter'):
                pos = len('filter(')
                f_end, start, end = parse_filters(q)

                filters = q[pos:f_end]
                result = user_manager.filter(filters, start=start, end=end)
            elif q.startswith('count('):
                pos = len('count(')
                f_end, start, end = parse_filters(q)

                filters = q[pos:f_end]
                result = user_manager.count(filters)
            elif q == 'properties':
                return JsonResponse(user_manager.list_filters(), safe=False)
            elif q == 'help':
                result = u"""
    Commands:
        - all(): Fetch all records
        - filter(some_filter): Fetch records based on `some_filter`
        - count(some_filters): Count records based on `some_filter`
        - properties: Show all acceptable attributes

    Examples of filter usage:
        - filter(age>30)
        - filter(age<20 and run_distance>500)

    Available data properties:
"""

                for f in user_manager.list_filters():
                    result += u"        %s" % f['name']
                    if f['has_options']:
                        result += ' / options: '
                        options_info = []

                        for o in f['get_options']:
                            options_info.append(u'%s%s' % (o[0], (' (%s)' % o[1]) if o[1] != o[0] else ''))

                        result += ','.join(options_info)

                    result += '\n'
            else:
                raise Exception('Unknown command: %s' % q)

            if q != 'help':
                result = simplejson.dumps(result, indent=4, ensure_ascii=False)

        except Exception as e:
            print(traceback.format_exc())

            status = 400
            result = str(e)

    return HttpResponse(result, status=status)


def console(request, pk):
    params = {
        'configuration': get_object_or_404(ConnectionConfiguration, pk=pk)
    }

    return render(request, 'anonymizer/connection/test_console.html', params)


class ConnectionConfigurationManualDeleteView(DeleteView):
    model = ConnectionConfiguration
    template_name = 'anonymizer/connection/delete.html'
    context_object_name = 'configuration'
    success_url = '/anonymizer/'


delete_view = ConnectionConfigurationManualDeleteView.as_view()


def access_keys(request, pk):
    """
    Activates a configuration
    """
    configuration = get_object_or_404(ConnectionConfiguration, pk=pk)

    if request.method == 'POST':
        key_name = request.POST.get('key_name', '')
        ConnectionAccessKey.objects.create(name=key_name, connection=configuration)

        return redirect('/anonymizer/connection/%d/access-keys/' % configuration.pk)
    else:
        return render(request, 'anonymizer/connection/configuration/access_keys.html', {
            'configuration': configuration
        })


def revoke_access_key(request, pk, key_id):
    """
    Activates a configuration
    """
    configuration = get_object_or_404(ConnectionConfiguration, pk=pk)
    access_key = get_object_or_404(ConnectionAccessKey, pk=key_id)

    if request.method == 'POST':
        access_key.is_active = False
        access_key.save()

    return redirect('/anonymizer/connection/%d/access-keys/' % configuration.pk)


def connnection_api_view(request, key, action='list'):
    try:
        access_key = ConnectionAccessKey.objects.get(key=key)
    except ConnectionAccessKey.DoesNotExist:
        return JsonResponse({
            'error': 'Access key not found.'
        }, status=404)

    if not access_key.is_active:
        return JsonResponse({
            'error': 'This access key has been revoked.'
        }, status=401)

    if not access_key.connection.is_active:
        return JsonResponse({
            'error': 'This connection is no longer available.'
        }, status=401)

    # get filters
    filters = request.GET.get('filters', '').replace('~', '=')

    # get offset & limit
    try:
        start = int(request.GET.get('offset', '0'))
    except (ValueError, TypeError):
        start = 0

    try:
        end = int(request.GET.get('limit')) + start
    except (ValueError, TypeError):
        end = None

    user_manager = access_key.connection.get_user_manager(token=access_key.connection.pk)
    status = 200

    if action == 'list':
        result = user_manager.filter(filters, start=start, end=end)
    elif action == 'count':
        result = {
            'count': user_manager.count(filters)
        }
    else:
        result = {
            'error': 'Invalid action.'
        }
        status = 400

    return JsonResponse(result, safe=False, status=status)
