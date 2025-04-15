<?php
defined('MOODLE_INTERNAL') || die();

function local_ollama_extend_settings_navigation($settingsnav, $context) {
    global $CFG;
    if (has_capability('local/ollama:ask', $context)) {
        $url = new moodle_url('/local/ollama/index.php');
        $settingsnav->add('Ollama', $url);
    }
}

// Webservice function
function local_ollama_ask($prompt) {
    require_capability('local/ollama:ask', context_system::instance());

    //  Execute Python
    $python_script = __DIR__ . '/scripts/ollama_helper.py';
    $escaped_prompt = escapeshellarg($prompt);
    $json_output = shell_exec("python3 {$python_script} {$escaped_prompt}");

    return [
        'success' => true,
        'response' => json_decode($json_output)
    ];
}