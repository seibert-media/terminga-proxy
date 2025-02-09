#!/usr/bin/env python3


from datetime import datetime, timedelta
from os import environ
import logging
import logging.handlers
import json

from flask import Flask, abort, jsonify, request
import psycopg2


def create_app():
    app = Flask(__name__)
    app.config.from_file(environ['APP_CONFIG'], load=json.load)
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
    hostgroup = request.args.get('hostgroup')
    if hostgroup is not None:
        hostgroup_join = '''
        inner join icinga_hostgroup_members on objs.object_id = icinga_hostgroup_members.host_object_id
        inner join icinga_hostgroups on icinga_hostgroup_members.hostgroup_id = icinga_hostgroups.hostgroup_id
        inner join icinga_objects objs_hostgroup on icinga_hostgroups.hostgroup_object_id = objs_hostgroup.object_id
        '''
        hostgroup_filter = '''
        and objs_hostgroup.name1 = %s
        '''
    else:
        hostgroup_join = ''
        hostgroup_filter = ''

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
            objs.name1,
            icinga_hoststatus.current_state,
            icinga_hoststatus.scheduled_downtime_depth,
            icinga_hoststatus.state_type,
            icinga_hoststatus.output,
            icinga_hoststatus.long_output,
            icinga_hoststatus.problem_has_been_acknowledged
        from icinga_objects objs
        {hostgroup_join}
        left join icinga_hoststatus on objs.object_id = icinga_hoststatus.host_object_id
        where
            objs.objecttype_id = 1 and
            objs.is_active = 1
            {hostgroup_filter}
        ;
        ''',
        (hostgroup,),
    )

    results = []
    for host_name, state, downtime_depth, state_type, output, long_output, acked in cur.fetchall():
        results.append({
            'type': 'Host',
            'attrs': {
                'acknowledgement': acked,
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
    servicegroup = request.args.get('servicegroup')
    if servicegroup is not None:
        servicegroup_join = '''
        inner join icinga_servicegroup_members on objs.object_id = icinga_servicegroup_members.service_object_id
        inner join icinga_servicegroups on icinga_servicegroup_members.servicegroup_id = icinga_servicegroups.servicegroup_id
        inner join icinga_objects objs_servicegroup on icinga_servicegroups.servicegroup_object_id = objs_servicegroup.object_id
        '''
        servicegroup_filter = '''
        and objs_servicegroup.name1 = %s
        '''
    else:
        servicegroup_join = ''
        servicegroup_filter = ''

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
            objs.name1,
            objs.name2,
            icinga_servicestatus.current_state,
            icinga_servicestatus.scheduled_downtime_depth,
            icinga_servicestatus.state_type,
            icinga_servicestatus.output,
            icinga_servicestatus.long_output,
            icinga_servicestatus.problem_has_been_acknowledged
        from icinga_objects objs
        {servicegroup_join}
        left join icinga_servicestatus on objs.object_id = icinga_servicestatus.service_object_id
        where
            objs.objecttype_id = 2 and
            objs.is_active = 1
            {servicegroup_filter}
        ;
        ''',
        (servicegroup,),
    )

    results = []
    for host_name, service_name, state, downtime_depth, state_type, output, long_output, acked in cur.fetchall():
        results.append({
            'type': 'Service',
            'attrs': {
                'acknowledgement': acked,
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
