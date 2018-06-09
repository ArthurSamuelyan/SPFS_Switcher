#!/bin/bash

mkdir A1
mkdir B1

mount -t tmpfs tmpfs A1
mount -t tmpfs tmpfs B1

cp -r A/* A1
cp -r B/* B1
