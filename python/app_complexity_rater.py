#!/usr/bin/env python
# The copyright in this work is owned by LAB3 Pty Ltd.
# You must not use, copy or reproduce this work, or create other works based on this work, without LAB3 Pty Ltd’s consent.
# LAB3 Pty Ltd reserves all rights to take legal action for any breach of copyright.

import os
from os import listdir
import numpy as np
import pandas as pd
from datetime import datetime
import re
import subprocess
import pyodbc
import sqlalchemy
import urllib
from sqlalchemy import create_engine

import argparse
import logging

import warnings
warnings.filterwarnings('ignore')
import time
import sys
absolute_path = os.path.dirname(os.path.realpath(__file__))
os.chdir(absolute_path)
sys.path.append("../../Utilities")
import error_output

script_name = 'AppComplexity'
config_type = 'app_sizing_complexity_has_run'

def app_metrics_aggregation(x, shared_servers):
    names = {
        'no_servers': x['vm_guid'].nunique(),
        'no_environments': x['environment'].nunique(),
        'vms_blocked_count': x[x['AzureVMReadiness'] == 'Not Ready']['vm_guid'].nunique(),
        'vms_ready_conditions_count': x[x['AzureVMReadiness'] == 'Ready With Conditions']['vm_guid'].nunique(),
        'app_criticality': x[x['app_criticality'].isin(['Critical', 'High'])]['app_guid'].nunique(),
        'data_classification': x[x['pii_data'].isin(['Confidential', 'Customer and Personal', 'Highly Protected', 1])]['app_guid'].nunique(),
        'disaster_recovery': x[x['disaster_recovery'] == 'Yes']['app_guid'].nunique(),
        'high_availability': x[x['high_availiability'] == 'Yes']['app_guid'].nunique(),
        'inherent_risk': x[x['inherent_risk'].isin(['Heightened', 'Extreme'])]['app_guid'].nunique(),
        'materiality': x[x['materiality'].isin(['Material'])]['app_guid'].nunique(),
        'sql_servers': x[x['ServerSubCategory'] == 'SQL Server']['vm_guid'].nunique(),
        'non_sql_db_servers': x[(x['ServerCategory'] == 'Database') & (x['ServerSubCategory'] != 'SQL Server')]['vm_guid'].nunique(),
        'rearchitect_flag': x[x['migration_strategy'] == 'Re-Architect']['app_guid'].nunique(),
        'replatform_flag': x[x['migration_strategy'] == 'Replatform/Refactor']['app_guid'].nunique(),
        'replace_flag': x[x['migration_strategy'] == 'Replace']['app_guid'].nunique(),
        'servers_shared_with_other_apps': x[x['vm_guid'].isin(shared_servers)]['vm_guid'].nunique()
        # 'hybrid_flag': x[x['migration_strategy'] == 'Hybrid']['app_guid'].nunique()
    }

    return pd.Series(names)

def script_progress(percentage,id,details_message,engine):
    
    status = 'InProgress' if percentage < 100.00 else 'Completed'
    timestamp = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with engine.begin() as connection:
        connection.execute(f"UPDATE dbo.ScriptExecutions SET last_edit_timestamp = '{timestamp}', percentage = {percentage}, status = '{status}', details = '{details_message}' WHERE id = {id};")
        log.info(f"Table dbo.ScriptExecutions updated with status '{status}' and percentage {percentage}%")

def script_run_state(run_id,engine,config_type):

    timestamp = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with engine.begin() as connection:
        user_name = pd.read_sql(f"SELECT last_edit_by FROM dbo.ScriptExecutions WHERE id = {run_id}",engine)['last_edit_by'][0]
        connection.execute(f""" UPDATE semi_static.Configuration_Settings 
                                SET [value] = 1,
                                    last_edit_by = '{user_name}',
                                    last_edit_timestamp = '{timestamp}'
                                WHERE config_type = '{config_type}'
                            """)

        log.info(f"Table semi_static.Configuration_Settings config_type '{config_type}' updated with value 1.")

def error_handling(error_message,id,engine):
    timestamp = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with engine.begin() as connection:
        connection.execute(f"UPDATE dbo.ScriptExecutions SET last_edit_timestamp = '{timestamp}',percentage = 100, status = 'Failed', details = '{error_message}' WHERE id = {id};")
    exit()


def load_data(log):
  
    # Create SQL Connections
    log.info(f'Creating SQL Connection, connecting to Assessments on localhost with a Trusted Connection')
    quoted = urllib.parse.quote_plus('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+os.environ['COMPUTERNAME']+';DATABASE=Assessments;Trusted_Connection=yes;')
    cnxn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER='+os.environ['COMPUTERNAME']+';DATABASE=Assessments;Trusted_Connection=yes;')

    engine = create_engine('mssql+pyodbc:///?odbc_connect={}'.format(quoted))
    cursor = cnxn.cursor()
    connection = engine.connect().execution_options(autocommit=True)

    if int(args.script_run_id) > 0: #script was executed from web app
        run_id = args.script_run_id

    else: #script was executed from backend
        log.info('Script executed from backend. Creating script run id.')
        timestamp = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        script_id = pd.read_sql(f"SELECT TOP 1 id FROM [static].sys_scripts WHERE script_function_name = '{script_name}'",cnxn)['id'][0]
        with engine.begin() as connection:
            connection.execute(f""" INSERT INTO dbo.ScriptExecutions(last_edit_by, last_edit_timestamp, executed_by, executed_at, is_deleted, script_id, execution_type, percentage, status, details)
                                    VALUES('NT AUTHORITY\SYSTEM','{timestamp}','Lab3Support@drmigrate.com','{timestamp}',0,{script_id},3,0,'InProgress',NULL)""")

        run_id = pd.read_sql(f"SELECT TOP 1 id FROM dbo.ScriptExecutions WHERE script_id = {script_id} AND percentage = 0 ORDER BY id DESC",cnxn)['id'][0]
        log.info(f'Assigned script run id is: {run_id}.')

    # Update progress in DB
    details_message = 'Analyzing application and associated server configurations...'
    script_progress(5,run_id,details_message,engine)
    time.sleep(1)

    # Execute stored procedure to map unassociated VMs
    log.info(f'Executing Stored Proc sp_MapUnassociatedVMs')
    cursor.execute(f'EXEC sp_MapUnassociatedVMs @light_run_version = 1;')
    cnxn.commit()

    # Iterate through the deduplicated Parquet files
    log.info('Iterating through the network files in C:/Network_Connections/')
    files = [f'C:/Network_Connections/{f.name}' for f in os.scandir('C:/Network_Connections/') if f.name.endswith('.parquet')]
    if files:
        nw_connections = [pd.read_parquet(f) for f in files]
        big_df = pd.concat(nw_connections, ignore_index=True)
        del nw_connections
    else:
        log.warning('No deduplicated network parquet files detected. Continuing without network data.')
        # try:
        #     with subprocess.Popen(['Pwsh', "C:/DrMigrate/Scripts/Python/NetworkDataDeduper.ps1"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT) as process:
        #         for line in process.stdout:
        #             log.info(line.decode().rsplit('\n')[0])
            
        #     log.info('Network parquet creator script completed successfully.')
        #     files = [f'C:/Network_Connections/{f.name}' for f in os.scandir('C:/Network_Connections/') if f.name.endswith('.parquet')]
        #     if files:
        #         nw_connections = [pd.read_parquet(f) for f in files]
        #         big_df = pd.concat(nw_connections, ignore_index=True)
        #         del nw_connections
        #     else:
        #         log.warning('There are no deduplicated Parquet files yet, even after running NetworkDataDeduper.ps1. Continuing without network data.')
        #         error_output.sendError("app_complex_nw_data")
        #         error_message = f'Dr Migrate did not detect available network data and was unable to calculate App Complexity as a result. Ensure that network data exists before running App Complexity again. If this issue persists, please contact Dr Migrate support providing the following reference: PY_NW_001_ERROR.'
        #         error_handling(error_message,run_id,engine)
        #         big_df = pd.DataFrame(columns=['Source server name', 'Source IP', 'Source application',
        #                                        'Source process', 'Destination server name', 'Destination IP',
        #                                        'Destination application', 'Destination process', 'Destination port',
        #                                        'traffic_type', 'pbi_dest_server_name', 'record_count'])

        # except Exception as e:
        #     log.error(e)
        #     tb = e.stderr.split("\n")
        #     log.error(''.join([traceback for traceback in tb if 'INFO' not in traceback and 'warning' not in traceback]))
        #     log.warning('There are no deduplicated Parquet files yet, and running NetworkDataDeduper.ps1 failed. Continuing without network data.')
        #     error_output.sendError("app_complex_nw_data")
        #     error_message = f'Dr Migrate did not detect available network data and was unable to calculate App Complexity as a result. Ensure that network data exists before running App Complexity again. If this issue persists, please contact Dr Migrate support providing the following reference: PY_NW_001_ERROR.'
        #     error_handling(error_message,run_id,engine)
        big_df = pd.DataFrame(columns=['Source server name', 'Source IP', 'Source application',
                                            'Source process', 'Destination server name', 'Destination IP',
                                            'Destination application', 'Destination process', 'Destination port',
                                            'traffic_type', 'pbi_dest_server_name', 'record_count'])

    # Update progress in DB
    script_progress(10,run_id,details_message,engine)
    time.sleep(1)

    # Cleanse the network traffic dataframe
    log.info('Cleansing the network traffic dataframe')
    try:
        big_df = big_df.applymap(lambda s: s.upper() if type(s) == str else s)

    except Exception as e:
        log.error(e)
        error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_NW_UNKNOWN_ERROR''."""
        error_handling(error_message,run_id,engine)

    # Update progress in DB
    script_progress(20,run_id,details_message,engine)
    time.sleep(1)

    big_df = big_df[(big_df['Source server name'] != big_df['Destination server name'])]

    # Update progress in DB
    script_progress(30,run_id,details_message,engine)
    time.sleep(1)

    log.info(f'Reading from SQL tables: GUID_Name_Mapping, Virtual_Machines_Info, ServerCategory, App_Questionnaire, Application & App_Complexity_Scorecard')
    
    try:
        # Application Server Mapping
        app_vm_df = pd.read_sql("SELECT DISTINCT gnm.application, gnm.app_guid, gnm.environment, gnm.machine, gnm.vm_guid, app.migration_strategy FROM dbo.GUID_Name_Mapping gnm LEFT JOIN dbo.Application app ON gnm.app_guid = app.app_guid WHERE gnm.application NOT LIKE 'Unassociated%'", engine)
        app_vm_df['machine'] = app_vm_df['machine'].str.upper()

        if len(app_vm_df) == 0:
            log.error(f"No applications with server mappings have been created yet, please create these before running the app complexity rater. Exiting script.")
            error_output.sendError("app_complex_app_server")
            error_message = 'No applications with server mappings have been created yet, please create them first before generating app complexity ratings.'
            error_handling(error_message,run_id,engine)

        # Virtual Machine level info
        vm_info_df = pd.read_sql("SELECT vm_guid, machine, AzureVMReadiness FROM dbo.Virtual_Machines_Info", engine)
        vm_info_df['machine'] = vm_info_df['machine'].str.upper()

        category_df = pd.read_sql("SELECT DisplayName, ServerCategory, ServerSubCategory FROM dbo.ServerCategory", engine)
        category_df['DisplayName'] = category_df['DisplayName'].str.upper()

        # sql_server_df = pd.read_sql("SELECT * FROM dbo.???", engine) # AM_Instances ???

        # App Level Info
        app_questionnaire_df = pd.read_sql("SELECT app_guid, app_criticality, pii_data, disaster_recovery, high_availiability, inherent_risk, materiality FROM dbo.App_Questionnaire", engine).fillna('')
        # app_tags_df = pd.read_sql("SELECT * FROM dbo.Tags WHERE tag_type = 1", engine)

        # Identify hybrid apps
        hybrid_df = pd.read_sql("""SELECT app_guid, CASE WHEN hybrid > 1 THEN 1 ELSE 0 END AS hybrid_flag 
                                    FROM(SELECT app_guid, COUNT(DISTINCT migration_strategy) AS hybrid 
                                        FROM dbo.GUID_Name_Mapping
                                        GROUP BY app_guid) t""",cnxn)

        # Update progress in DB
        details_message = 'Classifying applications based on complexity weighting settings...'
        script_progress(40,run_id,details_message,engine)
        time.sleep(1)

        # List of Likely Shared Services & Platform Applications
        platform_apps = pd.read_sql("SELECT DISTINCT app_guid FROM dbo.App_Questionnaire WHERE LOWER(app_function) LIKE 'platform%' OR LOWER(app_function) LIKE 'it tool%'", engine)['app_guid'].to_list()
        non_platform_apps = [x for x in (app_vm_df['app_guid'].drop_duplicates().to_list()) if x not in platform_apps]

        # Shared Servers with other apps
        shared_servers_df = (
            pd.read_sql("SELECT * FROM dbo.Shared_Servers_App_Associations", engine)
            .merge(app_vm_df[['app_guid', 'application']].drop_duplicates())
        )
        shared_servers = shared_servers_df['vm_guid'].unique().tolist()

        # Read in the complexity scorecard
        scorecard_df = pd.read_sql("SELECT * FROM dbo.App_Complexity_Active_Thresholds", engine)
        
    except pyodbc.InterfaceError as e: # incorrect db credentials
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)
    
    except pyodbc.DatabaseError as e: #closed db connection or incorrect server
        log.error(e)
        if re.search(r" \((\d+)\) ",str(e)) is None:    
            if 'closed connection' in str(e):
                error_code = 'CLOSED_CONNECTION'
            else:
                error_code = 'UNKNOWN'
        else:
            error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)

    except Exception as e:
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        if error_code.isdigit() == True:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        else:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_UNKNOWN_ERROR''."""
        error_handling(error_message,run_id,engine)

    # Update progress in DB
    script_progress(50,run_id,details_message,engine)
    time.sleep(2)

    # Create a dataframe of App-VM Associations, VM Info, App Questionnaire data and Server Categories
    log.info(f'Creating a dataframe of App-VM Associations, VM Info, App Questionnaire data and Server Categories')
    app_vm_info_df = (
        pd.merge(app_vm_df, vm_info_df, left_on='vm_guid', right_on='vm_guid', how='left')
        .merge(app_questionnaire_df, left_on='app_guid', right_on='app_guid', how='left')
        .merge(category_df, left_on='machine_x', right_on='DisplayName', how='left')
        .rename(columns={'machine_x': 'machine'})
    )

    # Find the max servers per environment for each app
    log.info(f'Finding the max servers per environment for each app')
    app_env_df = (
        app_vm_df.groupby(by=['app_guid', 'environment'], as_index=False)
        .agg({'vm_guid': 'nunique'})
        .groupby('app_guid', as_index=False)
        .agg({'vm_guid': 'max'})
        .rename(columns={'vm_guid': 'max_servers_per_environment'})
    )

    # Use the app_metrics_aggregation function to generate metrics
    log.info(f'Using the app_metrics_aggregation function to generate metrics')
    metrics_df = (
        app_vm_info_df.reset_index(drop=True)
        .groupby(by=['app_guid', 'application'], as_index=False)
        .apply(app_metrics_aggregation, shared_servers=shared_servers)
        .merge(hybrid_df, left_on='app_guid', right_on='app_guid', how='left')
        .merge(app_env_df, left_on='app_guid', right_on='app_guid', how='left')
    )

    # Create an app to app comms dataframe
    big_df['source_m'] = big_df['Source server name'].replace(np.NaN, '').str.upper()
    big_df['target_m'] = big_df['Destination server name'].replace(np.NaN, '').str.upper()
    app_to_app_comms = big_df[(big_df['source_m'] != big_df['target_m']) | (big_df['Destination server name'] != '') | (big_df['Source server name'] != '')]

    del big_df, app_vm_info_df, app_env_df

    app_to_app_comms = app_to_app_comms[app_to_app_comms['source_m'].notnull()]
    app_to_app_comms = app_to_app_comms[app_to_app_comms['target_m'].notnull()]

    # Update progress in DB
    script_progress(70,run_id,details_message,engine)
    time.sleep(1)

    app_vm_df = app_vm_df[app_vm_df['environment'].str.lower().str.startswith('prod', na=False)]

    # Create a mapping dictionary
    machine_to_app = dict(zip(app_vm_df['machine'], app_vm_df['app_guid']))

    # Map vm to app
    app_to_app_comms['source'] = app_to_app_comms['source_m'].map(machine_to_app)
    app_to_app_comms['target'] = app_to_app_comms['target_m'].map(machine_to_app)

    # Group edge list by applications
    log.info(f'Grouping edge list by applications')
    app_to_app_comms = (app_to_app_comms.groupby(['source', 'target'], sort=False)
                                    .agg(no_connections=('source', 'count'))
                                    .reset_index())

    # Finding inbound and outbound network connections (not including platform services)
    log.info(f'Finding inbound and outbound network connections (not including platform services)')
    app_to_app_comms = app_to_app_comms[(app_to_app_comms['source'] != app_to_app_comms['target'])]
    app_to_app_comms = app_to_app_comms[(app_to_app_comms['source'].isin(non_platform_apps)) & (app_to_app_comms['target'].isin(non_platform_apps))].reset_index(drop=True)

    # Outputing an edge list of app integrations
    # app_to_app_comms.to_parquet()

    outbound_comms = (
        app_to_app_comms[['source', 'no_connections']]
        .rename(columns={'source': 'app_guid'})
        .groupby(by=['app_guid'], as_index=False)
        .agg({'no_connections': 'sum'})
        .rename(columns={'no_connections': 'outbound_nw_connections'})
    )
    inbound_comms = (
        app_to_app_comms[['target', 'no_connections']]
        .rename(columns={'target': 'app_guid'})
        .groupby(by=['app_guid'], as_index=False)
        .agg({'no_connections': 'sum'})
        .rename(columns={'no_connections': 'inbound_nw_connections'})
    )
    app_nw_connections_count = pd.merge(outbound_comms, inbound_comms, how='outer')

    del outbound_comms, inbound_comms

    # Update progress in DB
    details_message = 'Finalizing complexity scores and assigning migration effort sizes...'
    script_progress(80,run_id,details_message,engine)
    time.sleep(1)

    # Finding app integrations (not including platform services)
    log.info(f'Finding app integrations (not including platform services)')
    app_integrations = (
        pd.concat([(
            app_to_app_comms[['source', 'target']]
            .rename(columns={'target': 'source', 'source': 'target'}))
            , app_to_app_comms[['source', 'target']]])
        .groupby(by=['target'], as_index=False)
        .agg({'source': 'nunique'})
        .rename(columns={'target': 'app_guid', 'source': 'app_integrations'})
    )

    # Add the network information onto the metrics dataframe
    log.info(f'Add the network information onto the metrics dataframe')
    metrics_df = (
        metrics_df.merge(app_nw_connections_count, left_on='app_guid', right_on='app_guid', how='left')
        .merge(app_integrations, left_on='app_guid', right_on='app_guid', how='left')
        .fillna(0)
        .drop_duplicates(subset=['app_guid'], keep='first')
    )
    metrics_df = metrics_df.astype({'outbound_nw_connections': 'int64', 'inbound_nw_connections': 'int64', 'app_integrations': 'int64'})

    # Pivoting and merging with the scorecard to analyse against thresholds 
    log.info(f'Pivoting and merging with the scorecard to analyse against thresholds')
    score_df = (
        metrics_df.melt(id_vars=['app_guid', 'application'], var_name='metric', value_name='value')
        .merge(scorecard_df, left_on='metric', right_on='metric', how='right')
    )

    # Update progress in DB
    script_progress(90,run_id,details_message,engine)
    time.sleep(1)

    # Comparing thresholds
    log.info(f'Comparing thresholds')
    score_df['low_complexity_flag'] = np.where(score_df['value'] <= score_df['low_complexity'], 0, 1)
    score_df['medium_complexity_flag'] = np.where(score_df['value'] <= score_df['medium_complexity'], 0, 1)
    score_df['high_complexity_flag'] = np.where(score_df['value'] <= score_df['high_complexity'], 0, 1)
    score_df['very_high_complexity_flag'] = np.where(score_df['value'] <= score_df['very_high_complexity'], 0, 1)
    score_df['extra_high_complexity_flag'] = np.where(score_df['value'] <= score_df['extra_high_complexity'], 0, 1)
    score_df['score'] = score_df['value'] * score_df['score_per_unit']

    # Summing thresholds flags and calculating score
    log.info(f'Summing thresholds flags and calculating score')
    results_df = (
        score_df.groupby(by=['app_guid', 'application'], as_index=False)
        .agg({
            'low_complexity_flag': 'sum',
            'medium_complexity_flag': 'sum',
            'high_complexity_flag': 'sum',
            'very_high_complexity_flag': 'sum',
            'extra_high_complexity_flag': 'sum',
            'score': 'sum'
        })
    )

    # Creating a list of complexity flag conditions
    conditions = [
        (results_df['low_complexity_flag'] == 0),
        (results_df['medium_complexity_flag'] == 0),
        (results_df['high_complexity_flag'] == 0),
        (results_df['very_high_complexity_flag'] == 0),
        (results_df['extra_high_complexity_flag'] == 0)
    ]

    # Declaring the values to insert if they are true
    values = [
        'Low Complexity', 
        'Medium Complexity', 
        'High Complexity', 
        'Very High Complexity', 
        'Extra High Complexity'
    ]

    # Assigning values to the Complexity column if app meets the thresholds
    log.info(f'Assigning values to the Complexity column if app meets the thresholds')
    results_df['Complexity'] = np.select(conditions, values)
    results_df['Complexity'].replace({'0': 'Unknown'}, inplace=True)

    # Removing application column from dataframes
    log.info(f'Removing application column from dataframes')
    metrics_df.drop(columns=['application'], inplace=True)
    results_df.drop(columns=['application'], inplace=True)

    # Truncate the table and write the new dataframe to SQL
    log.info(f'Truncating dbo.App_Complexity_Scores')
    try:
        cursor.execute(f'TRUNCATE TABLE dbo.App_Complexity_Scores;')
        cnxn.commit()

    except pyodbc.InterfaceError as e: # incorrect db credentials
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)
    
    except pyodbc.DatabaseError as e: #closed db connection or incorrect server
        log.error(e)
        if re.search(r" \((\d+)\) ",str(e)) is None:    
            if 'closed connection' in str(e):
                error_code = 'CLOSED_CONNECTION'
            else:
                error_code = 'UNKNOWN'
        else:
            error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)

    except Exception as e:
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        if error_code.isdigit() == True:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        else:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_UNKNOWN_ERROR''."""
        error_handling(error_message,run_id,engine)


    # Load the data into the truncated table
    try:            
        log.info(f'Loading data for dbo.App_Complexity_Scores')
        metrics_df.to_sql(f'App_Complexity_Scores', con=engine, if_exists='append', schema='dbo', index=False)
    except pyodbc.InterfaceError as e: # incorrect db credentials
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_output.sendError('app_complexity_data_load_error')
        error_handling(error_message,run_id,engine)
    
    except pyodbc.DatabaseError as e: #closed db connection or incorrect server
        log.error(e)
        if re.search(r" \((\d+)\) ",str(e)) is None:    
            if 'closed connection' in str(e):
                error_code = 'CLOSED_CONNECTION'
            else:
                error_code = 'UNKNOWN'
        else:
            error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_output.sendError('app_complexity_data_load_error')
        error_handling(error_message,run_id,engine)

    except Exception as e:
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        if error_code.isdigit() == True:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        else:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_UNKNOWN_ERROR''."""
        error_handling(error_message,run_id,engine)
        
    # Write back to the Application table in SQL
    log.info(f"Writing the Complexity ratings back to the dbo.Application table in SQL")
    try:
        cursor = cnxn.cursor()
        cursor.execute("UPDATE dbo.Application SET complexity_rating = NULL, complexity_score = NULL")
        for index, row in results_df.iterrows():
            cursor.execute("UPDATE dbo.Application SET complexity_rating = ?, complexity_score = ? WHERE app_guid = ?", (row.Complexity, row.score, row.app_guid))
        cnxn.commit()

    except pyodbc.InterfaceError as e: # incorrect db credentials
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)
    
    except pyodbc.DatabaseError as e: #closed db connection or incorrect server
        log.error(e)
        if re.search(r" \((\d+)\) ",str(e)) is None:    
            if 'closed connection' in str(e):
                error_code = 'CLOSED_CONNECTION'
            else:
                error_code = 'UNKNOWN'
        else:
            error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        error_message = f"""Dr Migrate encountered an error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        error_handling(error_message,run_id,engine)

    except Exception as e:
        log.error(e)
        error_code = re.search(r" \((\d+)\) ",str(e)).group(1)
        if error_code.isdigit() == True:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_{error_code}_ERROR''."""
        else:
            error_message = f"""Dr Migrate encountered an unexpected error. Please contact Dr Migrate Support providing the following error code: ''PY_DB_UNKNOWN_ERROR''."""
        error_handling(error_message,run_id,engine)
    
    # Update progress in DB
    script_run_state(run_id,engine,config_type)
    script_progress(100,run_id,details_message,engine)
    cursor.close()


def set_logging():
    # create logger
    level = "INFO"
    if args.verbose:
        print("sss")
        level = "DEBUG"
    logger = logging.getLogger("Dr Migrate Logging")
    logger.setLevel(level)
    
    # create console handler and set level to debug
    ch = logging.StreamHandler()
    ch.setLevel(level)
    
    # create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # add formatter to ch
    ch.setFormatter(formatter)
    
    # add ch to logger
    logger.addHandler(ch)
    return logger

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Dr Migrate Application Complexity Rater.")
    parser.add_argument(
        "--verbose",
        dest="verbose",
        action="store_true",
        help="Verbose Logging",
    )
    parser.add_argument(
        "-id",
        "--run_id",
        dest="script_run_id",
        required=False,
        default=0,
        help='script_run_id for current app complexity run.',
    )
    args = parser.parse_args()
    
    log = set_logging()
    load_data(log)