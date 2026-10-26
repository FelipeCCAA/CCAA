import assert from 'node:assert/strict';
import test from 'node:test';
import { mensajePoliticaContinuidad, puedeContinuarPendiente, payloadContinuidadPendiente, sufijoAvisosCalidad } from '../src/services/continuidad-calidad.ts';

test('el aviso exige política activa y recuerda la liberación final', () => {
  assert.equal(mensajePoliticaContinuidad(undefined), null);
  assert.equal(mensajePoliticaContinuidad({ avisos_intermedios: false, mensaje: 'No activo' }), null);
  assert.equal(mensajePoliticaContinuidad({ avisos_intermedios: true, mensaje: '' }), 'Producción con Calidad pendiente: se puede continuar; la liberación final sigue siendo obligatoria.');
});
test('la continuidad requiere habilitación explícita del servidor y permiso operacional', () => {
  assert.equal(puedeContinuarPendiente(true, { continuidad_pendiente_disponible: true }), true);
  assert.equal(puedeContinuarPendiente(false, { continuidad_pendiente_disponible: true }), false);
  assert.equal(puedeContinuarPendiente(true, {}), false);
  assert.equal(puedeContinuarPendiente(true, { continuidad_pendiente_disponible: false }), false);
});
test('el pedido conserva el motivo auditado y no contiene firma ni liberación', () => {
  assert.deepEqual(payloadContinuidadPendiente(), { motivo: 'Continuidad operacional con Calidad pendiente' });
});
test('las opciones presentan avisos informados sin inventar liberación', () => {
  assert.equal(sufijoAvisosCalidad(undefined), '');
  assert.equal(sufijoAvisosCalidad([]), '');
  assert.equal(sufijoAvisosCalidad(['Análisis pendiente', 'Firma pendiente']), ' · Análisis pendiente · Firma pendiente');
});
