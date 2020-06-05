#!/usr/bin/env python3


from datetime import datetime, timedelta
from os import environ
import logging
import logging.handlers

from flask import Flask, abort, jsonify, request
import psycopg2


def create_app():
    app = Flask(__name__)
    app.config.from_json(environ['APP_CONFIG'])
    if not app.debug:
        stream_handler = logging.handlers.SysLogHandler(address='/dev/log')
        app.logger.addHandler(stream_handler)
        app.logger.setLevel(logging.INFO)
    return app


app = create_app()


def check_freshness(cur):
    cur.execute('select status_update_time from icinga_programstatus;')
    lst = list(cur.fetchall())
    if datetime.utcnow() - lst[0][0] > timedelta(minutes=5):
        abort(503)


@app.route('/api/v1/objects/hosts')
def hosts():
    varname = request.args.get('host_filter_custom_varname')
    varvalue = request.args.get('host_filter_custom_varvalue')
    if varname is not None and varvalue is not None:
        custom_var_join = 'left join icinga_customvariables on icinga_objects.object_id = icinga_customvariables.object_id'
        custom_var_filter = '''
        and (
            icinga_customvariables.varname = %s and
            icinga_customvariables.varvalue = %s
        )
        '''
    else:
        custom_var_join = ''
        custom_var_filter = ''

    conn = psycopg2.connect(
        dbname=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASS'],
    )
    cur = conn.cursor()

    check_freshness(cur)

    cur.execute(
        f'''
        select
            icinga_objects.name1,
            icinga_hoststatus.current_state,
            icinga_hoststatus.scheduled_downtime_depth,
            icinga_hoststatus.state_type,
            icinga_hoststatus.output,
            icinga_hoststatus.long_output
        from icinga_objects
        left join icinga_hoststatus on icinga_objects.object_id = icinga_hoststatus.host_object_id
        {custom_var_join}
        where
            icinga_objects.objecttype_id = 1 and
            icinga_objects.is_active = 1
            {custom_var_filter}
        ;
        ''',
        (varname, varvalue),
    )

    results = []
    for host_name, state, downtime_depth, state_type, output, long_output in cur.fetchall():
        results.append({
            'type': 'Host',
            'attrs': {
                'display_name': host_name,
                'downtime_depth': downtime_depth,
                'state': state,
                'state_type': state_type,
                'last_check_result': {
                    'output': output + '\n' + long_output.replace('\\n', '\n'),
                },
            },
        })

    cur.close()
    conn.close()

    return jsonify({'results': results})


@app.route('/api/v1/objects/services')
def services():
    varname = request.args.get('service_filter_custom_varname')
    varvalue = request.args.get('service_filter_custom_varvalue')
    if varname is not None and varvalue is not None:
        custom_var_join = '''
        left join icinga_services on icinga_services.service_object_id = icinga_servicestatus.service_object_id
        left join icinga_customvariables on icinga_services.service_object_id = icinga_customvariables.object_id
        '''
        custom_var_filter = '''
        and (
            icinga_customvariables.varname = %s and
            icinga_customvariables.varvalue = %s
        )
        '''
    else:
        custom_var_join = ''
        custom_var_filter = ''

    conn = psycopg2.connect(
        dbname=app.config['DB_NAME'],
        user=app.config['DB_USER'],
        password=app.config['DB_PASS'],
    )
    cur = conn.cursor()

    check_freshness(cur)

    cur.execute(
        f'''
        select
            icinga_objects.name1,
            icinga_objects.name2,
            icinga_servicestatus.current_state,
            icinga_servicestatus.scheduled_downtime_depth,
            icinga_servicestatus.state_type,
            icinga_servicestatus.output,
            icinga_servicestatus.long_output
        from icinga_objects
        left join icinga_servicestatus on icinga_objects.object_id = icinga_servicestatus.service_object_id
        {custom_var_join}
        where
            icinga_objects.objecttype_id = 2 and
            icinga_objects.is_active = 1
            {custom_var_filter}
        ;
        ''',
        (varname, varvalue),
    )

    results = []
    for host_name, service_name, state, downtime_depth, state_type, output, long_output in cur.fetchall():
        results.append({
            'type': 'Service',
            'attrs': {
                'host_name': host_name,
                'display_name': service_name,
                'downtime_depth': downtime_depth,
                'state': state,
                'state_type': state_type,
                'last_check_result': {
                    'output': output + '\n' + long_output.replace('\\n', '\n'),
                },
            },
        })

    cur.close()
    conn.close()

    return jsonify({'results': results})


if __name__ == '__main__':
    app.run(host='::')
