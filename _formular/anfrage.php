<?php
// DUCT TAPE – Booking-Anfrageformular
// Liegt auf dem IONOS-Webspace unter https://formular.ducttape.berlin/anfrage.php
// Nimmt das Formular von ducttape.berlin/anfrage.html (bzw. /en/enquiry.html) an,
// schickt die Anfrage als Mail an booking@ und leitet auf die Danke-Seite weiter.
// Es wird nichts gespeichert: keine Datenbank, keine Logdatei.

const EMPFAENGER = 'booking@ducttape.berlin';
const ABSENDER   = 'info@ducttape.berlin';   // muss ein Postfach bei IONOS sein
const SITE       = 'https://ducttape.berlin';

$lang  = (($_POST['lang'] ?? '') === 'en') ? 'en' : 'de';
$danke = SITE . ($lang === 'en' ? '/en/thank-you.html' : '/danke.html');
$form  = SITE . ($lang === 'en' ? '/en/enquiry.html' : '/anfrage.html');

function weiter($url) { header('Location: ' . $url, true, 303); exit; }
function feld($k, $max = 300) {
  $v = trim((string)($_POST[$k] ?? ''));
  $v = str_replace(["\r\n", "\r"], "\n", $v);
  return mb_substr($v, 0, $max, 'UTF-8');
}
function zeile($v) { return trim(preg_replace('/[\r\n\t]+/', ' ', $v)); }

if ($_SERVER['REQUEST_METHOD'] !== 'POST') weiter($form);

// Nur Anfragen von der eigenen Website annehmen
$origin = $_SERVER['HTTP_ORIGIN'] ?? '';
if ($origin !== '' && !in_array($origin, [SITE, 'https://www.ducttape.berlin'], true)) weiter($form . '?fehler=1');

// Spamschutz: verstecktes Feld muss leer sein, Formular nicht schneller als 3 Sekunden ausgefüllt
if (feld('website') !== '') weiter($danke);
$t = (int)feld('t', 20);
if ($t > 0 && time() - $t < 3) weiter($danke);

$name     = zeile(feld('name', 120));
$email    = zeile(feld('email', 160));
$programm = zeile(feld('programm', 80));
if ($name === '' || $programm === '' || !filter_var($email, FILTER_VALIDATE_EMAIL) || feld('einwilligung', 5) !== 'ja') {
  weiter($form . '?fehler=1');
}

$acts = ['' => 'Noch offen', 'kollektiv' => 'Das ganze Kollektiv', 'emi' => 'EMI', 'symba' => 'Symba', 'magda' => 'Magda von Pfeffer'];
$act  = $acts[feld('act', 20)] ?? 'Noch offen';
$datum = feld('datum', 20);
if (preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $datum, $m)) $datum = "$m[3].$m[2].$m[1]";

$zeilen = [
  'Name'                => $name,
  'E-Mail'              => $email,
  'Telefon'             => zeile(feld('telefon', 60)),
  'Firma / Organisation'=> zeile(feld('firma', 160)),
  'Programm'            => $programm,
  'Act'                 => $act,
  'Datum'               => zeile($datum),
  'Ort / Location'      => zeile(feld('ort', 160)),
  'Gäste'               => zeile(feld('gaeste', 10)),
  'Anlass'              => zeile(feld('anlass', 160)),
  'Gefunden über'       => zeile(feld('gefunden', 60)),
  'Quelle (Tracking)'   => zeile(feld('quelle', 300)),
  'Sprache'             => strtoupper($lang),
];
$text = "Neue Booking-Anfrage über ducttape.berlin\n\n";
foreach ($zeilen as $k => $v) if ($v !== '') $text .= $k . ':' . str_repeat(' ', max(1, 22 - mb_strlen($k . ':', 'UTF-8'))) . $v . "\n";
$nachricht = feld('nachricht', 5000);
if ($nachricht !== '') $text .= "\nNachricht:\n" . $nachricht . "\n";
$text .= "\nAntworten geht direkt an " . $email . ".\n";

$betreff = 'Booking-Anfrage: ' . $programm . ' – ' . $name . ($datum !== '' ? ' (' . $datum . ')' : '');
$header  = implode("\r\n", [
  'From: ' . mb_encode_mimeheader('DUCT TAPE Website', 'UTF-8') . ' <' . ABSENDER . '>',
  'Reply-To: ' . mb_encode_mimeheader($name, 'UTF-8') . ' <' . $email . '>',
  'MIME-Version: 1.0',
  'Content-Type: text/plain; charset=UTF-8',
  'Content-Transfer-Encoding: 8bit',
]);

$ok = mail(EMPFAENGER, mb_encode_mimeheader($betreff, 'UTF-8'), $text, $header, '-f' . ABSENDER);
weiter($ok ? $danke : $form . '?fehler=1');
