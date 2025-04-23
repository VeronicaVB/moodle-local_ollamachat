<?php
require_once(__DIR__ . '/../../config.php');
require_once($CFG->libdir . '/adminlib.php');
require_once(__DIR__ . '/lib.php');

defined('MOODLE_INTERNAL') || die();

// Requerir login y permisos
require_login();
$context = context_system::instance();
require_capability('local/ollamachat:ask', $context);

// Configurar la página
$PAGE->set_context($context);
$PAGE->set_url(new moodle_url('/local/ollamachat/index.php'));
$PAGE->set_title(get_string('pluginname', 'local_ollamachat'));
$PAGE->set_heading(get_string('pluginname', 'local_ollamachat'));
$PAGE->requires->css(new moodle_url($CFG->wwwroot . '/local/ollamachat/styles.css'));

echo $OUTPUT->header();

$templatecontext = [
    'wwwroot' => $CFG->wwwroot,
    'assistantname' => get_config('local_ollamachat', 'assistant_name'),
];

echo $OUTPUT->render_from_template('local_ollamachat/chat_ui', $templatecontext);
// Add amd scripts.
$PAGE->requires->js_call_amd('local_ollamachat/controls', 'init',[]);

echo $OUTPUT->footer();