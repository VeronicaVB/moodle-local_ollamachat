<?php
defined('MOODLE_INTERNAL') || die();
$capabilities = [
    'local/ollamachat:ask' => [
        'captype' => 'read',
        'contextlevel' => CONTEXT_SYSTEM,
        'archetypes' => [
            'manager' => CAP_ALLOW,
            'teacher' => CAP_ALLOW,
        ],
    ],
];