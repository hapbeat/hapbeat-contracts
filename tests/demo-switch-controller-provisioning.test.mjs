import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const root = new URL('..', import.meta.url);
const valid = JSON.parse(await readFile(new URL('fixtures/demo-switch-controller-provisioning.valid.json', root)));
const invalid = JSON.parse(await readFile(new URL('fixtures/demo-switch-controller-provisioning.invalid.json', root)));
const identifier = /^[a-z0-9][a-z0-9._-]{0,63}$/;
const ipv4 = /^(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)(?:\.(?:25[0-5]|2[0-4]\d|1\d{2}|[1-9]?\d)){3}$/;
const clearFields = ['wifi_ssid', 'wifi_password', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret'];

function fail(message) { throw new Error(message); }
function assertObject(value, name) { if (!value || Array.isArray(value) || typeof value !== 'object') fail(`${name} must be an object`); }
function assertOnly(value, allowed, name) { for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`${name}.${key} is not allowed`); }
function assertId(value, name, nullable = false) { if (nullable && value === null) return; if (typeof value !== 'string' || !identifier.test(value)) fail(`${name} is invalid`); }
function assertUtf8(value, max, name) { if (typeof value !== 'string' || value.length === 0 || Buffer.byteLength(value, 'utf8') > max) fail(`${name} is invalid`); }
function assertHmdIp(value) {
  if (typeof value !== 'string' || !ipv4.test(value)) fail('hmd_ip syntax is invalid');
  const octets = value.split('.').map(Number);
  if (octets[0] === 0 || octets[0] === 127 || octets[0] >= 224 || value === '255.255.255.255') fail('hmd_ip must be unicast');
}
function assertVersion(frame) { if (frame.version !== 1) fail('version must be 1'); }

function validateConfig(config) {
  assertObject(config, 'config');
  const fields = ['wifi_ssid', 'wifi_password_set', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret_set', 'allow_unsigned', 'isolated_lan', 'next_sequence'];
  assert.deepEqual(Object.keys(config).sort(), fields.sort());
  if (config.wifi_ssid !== null) assertUtf8(config.wifi_ssid, 32, 'wifi_ssid');
  if (config.hmd_ip !== null) assertHmdIp(config.hmd_ip);
  assertId(config.controller_id, 'controller_id');
  for (const key of ['target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id']) assertId(config[key], key, true);
  for (const key of ['wifi_password_set', 'shared_secret_set', 'allow_unsigned', 'isolated_lan']) if (typeof config[key] !== 'boolean') fail(`${key} must be boolean`);
  if (!Number.isSafeInteger(config.next_sequence) || config.next_sequence < 1) fail('next_sequence is invalid');
}

function validateUpdate(update) {
  assertObject(update, 'config update');
  if (Object.keys(update).length === 0) fail('config update is empty');
  const values = ['wifi_ssid', 'wifi_password', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret', 'allow_unsigned', 'isolated_lan'];
  assertOnly(update, [...values, ...clearFields.map((field) => `clear_${field}`)], 'config update');
  if ('wifi_ssid' in update) assertUtf8(update.wifi_ssid, 32, 'wifi_ssid');
  for (const key of ['wifi_password', 'shared_secret']) if (key in update) assertUtf8(update[key], 256, key);
  if ('hmd_ip' in update) assertHmdIp(update.hmd_ip);
  for (const key of ['controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id']) if (key in update) assertId(update[key], key);
  for (const field of clearFields) {
    const clearKey = `clear_${field}`;
    if (clearKey in update && typeof update[clearKey] !== 'boolean') fail(`${clearKey} must be boolean`);
    if (update[clearKey] === true && field in update) fail(`${field} conflicts with ${clearKey}`);
  }
  for (const key of ['allow_unsigned', 'isolated_lan']) if (key in update && typeof update[key] !== 'boolean') fail(`${key} must be boolean`);
  if (update.allow_unsigned === true && update.isolated_lan !== true) fail('unsigned mode requires isolated LAN opt-in');
  if (update.allow_unsigned === true && 'shared_secret' in update) fail('unsigned mode cannot set a shared secret');
}

function validateFrame(frame) {
  assertObject(frame, 'frame');
  assertVersion(frame);
  if (frame.type === 'get_config' || frame.type === 'factory_reset' || frame.type === 'reboot') {
    assert.deepEqual(Object.keys(frame).sort(), ['id', 'type', 'version']);
    assertId(frame.id, 'id');
    return;
  }
  if (frame.type === 'set_config') {
    assert.deepEqual(Object.keys(frame).sort(), ['config', 'id', 'type', 'version']);
    assertId(frame.id, 'id');
    validateUpdate(frame.config);
    return;
  }
  if (frame.type !== 'response') fail('type is invalid');
  if (frame.response === 'config') { assertId(frame.id, 'id'); assert.deepEqual(Object.keys(frame).sort(), ['config', 'id', 'response', 'type', 'version']); validateConfig(frame.config); return; }
  if (frame.response === 'status') {
    assertId(frame.id, 'id');
    assert.deepEqual(Object.keys(frame).sort(), ['id', 'response', 'status', 'type', 'version']);
    assertObject(frame.status, 'status');
    const statusPairs = { set_config: 'updated', factory_reset: 'reset', reboot: 'rebooting' };
    if (statusPairs[frame.status.command] !== frame.status.state || Object.keys(frame.status).length !== 2) fail('status is invalid');
    return;
  }
  if (frame.response === 'error') {
    assertId(frame.id, 'id', true);
    assert.deepEqual(Object.keys(frame).sort(), ['error', 'id', 'response', 'type', 'version']);
    assertObject(frame.error, 'error');
    if (!['invalid_json', 'line_too_long', 'unsupported_version', 'unknown_command', 'invalid_request', 'invalid_config', 'conflicting_update', 'write_failed', 'busy'].includes(frame.error.code) || typeof frame.error.message !== 'string' || Buffer.byteLength(frame.error.message, 'utf8') > 256 || Object.keys(frame.error).length !== 2) fail('error is invalid');
    return;
  }
  fail('response is invalid');
}

test('valid fixtures conform and fit one serial line', () => {
  for (const { name, frame } of valid) {
    assert.doesNotThrow(() => validateFrame(frame), name);
    assert.ok(Buffer.byteLength(`${JSON.stringify(frame)}\n`, 'utf8') <= 1024, `${name} exceeds the serial line limit`);
  }
});

test('invalid fixtures are rejected', () => {
  for (const { name, frame } of invalid) assert.throws(() => validateFrame(frame), name);
});
