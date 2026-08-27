import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { test } from 'node:test';

const root = new URL('..', import.meta.url);
const valid = JSON.parse(await readFile(new URL('fixtures/demo-switch-controller-provisioning.valid.json', root)));
const invalid = JSON.parse(await readFile(new URL('fixtures/demo-switch-controller-provisioning.invalid.json', root)));
const schema = JSON.parse(await readFile(new URL('schemas/demo-switch-controller-provisioning.schema.json', root)));
const identifier = /^[a-z0-9][a-z0-9._-]{0,63}$/;

function fail(message) { throw new Error(message); }
function object(value, name) { if (!value || Array.isArray(value) || typeof value !== 'object') fail(`${name} must be an object`); }
function only(value, allowed, name) { for (const key of Object.keys(value)) if (!allowed.includes(key)) fail(`${name}.${key} is not allowed`); }
function text(value, max, name) { if (typeof value !== 'string' || !value || Buffer.byteLength(value, 'utf8') > max) fail(`${name} is invalid`); }
function id(value, name, nullable = false) { if (nullable && value === null) return; if (typeof value !== 'string' || !identifier.test(value)) fail(`${name} is invalid`); }
function hmd(value) { if (value === null) return; if (typeof value !== 'string' || !/^(?:\d{1,3}\.){3}\d{1,3}$/.test(value)) fail('hmd_ip is invalid'); const octets = value.split('.').map(Number); if (octets.some((octet) => octet > 255) || octets[0] === 0 || octets[0] === 127 || octets[0] >= 224) fail('hmd_ip must be unicast'); }
function profile(value, response) {
  object(value, 'wifi profile');
  only(value, response ? ['ssid', 'open', 'wifi_password_set'] : ['ssid', 'open', 'wifi_password'], 'wifi profile');
  text(value.ssid, 32, 'wifi profile ssid');
  if ('open' in value && typeof value.open !== 'boolean') fail('wifi profile open is invalid');
  if (response) { if (typeof value.open !== 'boolean' || typeof value.wifi_password_set !== 'boolean' || value.open === value.wifi_password_set) fail('wifi profile redaction is invalid'); }
  else if (value.open === true && 'wifi_password' in value) fail('open profile cannot include password');
}
function config(value) {
  object(value, 'config');
  const fields = ['wifi_profiles', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret_set', 'allow_unsigned', 'isolated_lan', 'next_sequence'];
  assert.deepEqual(Object.keys(value).sort(), fields.sort());
  if (!Array.isArray(value.wifi_profiles) || value.wifi_profiles.length > 5) fail('wifi_profiles is invalid');
  value.wifi_profiles.forEach((entry) => profile(entry, true));
  if (new Set(value.wifi_profiles.map((entry) => entry.ssid)).size !== value.wifi_profiles.length) fail('wifi profile SSIDs must be unique');
  id(value.controller_id, 'controller_id');
  hmd(value.hmd_ip);
  for (const key of ['target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id']) id(value[key], key, true);
  for (const key of ['shared_secret_set', 'allow_unsigned', 'isolated_lan']) if (typeof value[key] !== 'boolean') fail(`${key} is invalid`);
  if (!Number.isSafeInteger(value.next_sequence) || value.next_sequence < 1) fail('next_sequence is invalid');
}
function update(value) {
  object(value, 'config update'); if (!Object.keys(value).length) fail('config update is empty');
  const values = ['wifi_profiles', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret', 'allow_unsigned', 'isolated_lan'];
  const clears = ['wifi_profiles', 'hmd_ip', 'controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id', 'shared_secret'];
  only(value, [...values, ...clears.map((name) => `clear_${name}`)], 'config update');
  if ('wifi_profiles' in value) { if (!Array.isArray(value.wifi_profiles) || !value.wifi_profiles.length || value.wifi_profiles.length > 5) fail('wifi_profiles is invalid'); value.wifi_profiles.forEach((entry) => profile(entry, false)); if (new Set(value.wifi_profiles.map((entry) => entry.ssid)).size !== value.wifi_profiles.length) fail('wifi profile SSIDs must be unique'); }
  if (value.clear_wifi_profiles === true && 'wifi_profiles' in value) fail('wifi_profiles conflicts with clear_wifi_profiles');
  for (const key of clears) if (`clear_${key}` in value && typeof value[`clear_${key}`] !== 'boolean') fail(`clear_${key} is invalid`);
  for (const key of clears) if (value[`clear_${key}`] === true && key in value) fail(`${key} conflicts with clear_${key}`);
  for (const key of ['controller_id', 'target_a_demo_id', 'target_b_demo_id', 'target_c_demo_id']) if (key in value) id(value[key], key);
  if ('shared_secret' in value) text(value.shared_secret, 256, 'shared_secret');
  if ('hmd_ip' in value) hmd(value.hmd_ip);
  if (value.allow_unsigned === true && value.isolated_lan !== true) fail('unsigned requires isolated LAN');
}
function frame(value) {
  object(value, 'frame'); if (value.version !== 1) fail('version is invalid');
  if (['get_config', 'factory_reset', 'reboot'].includes(value.type)) { assert.deepEqual(Object.keys(value).sort(), ['id', 'type', 'version']); id(value.id, 'id'); return; }
  if (value.type === 'set_config') { assert.deepEqual(Object.keys(value).sort(), ['config', 'id', 'type', 'version']); id(value.id, 'id'); update(value.config); return; }
  if (value.type !== 'response') fail('type is invalid');
  if (value.response === 'config') { assert.deepEqual(Object.keys(value).sort(), ['config', 'id', 'response', 'type', 'version']); id(value.id, 'id'); config(value.config); return; }
  if (value.response === 'status') { id(value.id, 'id'); const pairs = { set_config: 'updated', factory_reset: 'reset', reboot: 'rebooting' }; if (!value.status || pairs[value.status.command] !== value.status.state || Object.keys(value.status).length !== 2) fail('status is invalid'); return; }
  if (value.response === 'error') { id(value.id, 'id', true); return; }
  fail('response is invalid');
}
test('valid fixtures conform and fit one serial line', () => { for (const { name, frame: value } of valid) { assert.doesNotThrow(() => frame(value), name); assert.ok(Buffer.byteLength(`${JSON.stringify(value)}\n`, 'utf8') <= 3072, `${name} exceeds the serial line limit`); } });
test('invalid fixtures are rejected', () => { for (const { name, frame: value } of invalid) assert.throws(() => frame(value), name); });
test('Wi-Fi profile schema documents SSID uniqueness and custom validation enforces it', () => {
  for (const profiles of [schema.$defs.config.properties.wifi_profiles, schema.$defs.configUpdate.properties.wifi_profiles]) {
    assert.equal(profiles.uniqueItems, true);
    assert.equal(profiles['x-uniqueBy'], 'ssid');
  }
  assert.throws(() => update({ wifi_profiles: [{ ssid: 'DemoLan', wifi_password: 'one' }, { ssid: 'DemoLan', wifi_password: 'two' }] }));
});
test('schema documents the 3072-byte NDJSON limit and maximum five-profile update fits it', () => {
  assert.equal(schema['x-ndjsonLineLimitBytes'], 3072);
  const wifiProfiles = Array.from({ length: 5 }, (_, index) => ({
    ssid: `ssid-${index}${'s'.repeat(26)}`,
    wifi_password: 'p'.repeat(256),
  }));
  const value = { version: 1, type: 'set_config', id: 'five-profiles', config: { wifi_profiles: wifiProfiles } };
  assert.doesNotThrow(() => frame(value));
  const length = Buffer.byteLength(`${JSON.stringify(value)}\n`, 'utf8');
  assert.ok(length > 1024);
  assert.ok(length <= 3072);
});
