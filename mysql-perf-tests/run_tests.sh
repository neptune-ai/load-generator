#!/bin/sh

MYSQL_HOST=$1
MYSQL_USER=$2
MYSQL_PASSWORD=$3
NUM_THREADS=$4
VERBOSITY=5

sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_insert prepare
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_insert run
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_insert cleanup

sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_point_select prepare
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_point_select run
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_point_select cleanup

sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_index prepare
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_index run
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_index cleanup

sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_non_index prepare
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_non_index run
sysbench --threads=$NUM_THREADS --time=$TIME --verbosity=$VERBOSITY --mysql-host=$MYSQL_HOST --mysql-user=$MYSQL_USER --mysql-password=$MYSQL_PASSWORD oltp_update_non_index cleanup