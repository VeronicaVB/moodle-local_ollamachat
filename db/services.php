<?php
defined('MOODLE_INTERNAL') || die();

$functions = [
    'local_ollamachat_ask_ollama' => [
        'classname'   => 'local_ollamachat_external', // The name of the external class.
        'methodname'  => 'ask_ollama',               // The name of the method in the class.
        'classpath'   => 'local/ollamachat/externallib.php', // Path to the external class.
        'description' => 'Ask a question to Ollama.', // Description of the web service function.
        'type'        => 'read',                     // Type of operation: read or write.
        // 'capabilities'=> 'local/ollamachat:use',     // Required capability.
    ],
    'local_ollamachat_ask_with_knowledge' => [
        'classname'   => 'local_ollamachat_external', // The name of the external class.
        'methodname'  => 'ask_with_knowledge',               // The name of the method in the class.
        'classpath'   => 'local/ollamachat/externallib.php', // Path to the external class.
        'description' => 'Ask a question to Ollama you can use kb content.', // Description of the web service function.
        'type'        => 'read',                     // Type of operation: read or write.
        // 'capabilities'=> 'local/ollamachat:use',     // Required capability.
    ],
];