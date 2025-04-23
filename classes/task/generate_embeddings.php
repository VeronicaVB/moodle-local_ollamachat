<?php

namespace local_ollamachat\task;

defined('MOODLE_INTERNAL') || die();

require_once($CFG->libdir . '/filelib.php');

class generate_embeddings extends \core\task\scheduled_task {

    public function get_name() {
        return get_string('generate_embeddings_task', 'local_ollamachat');
    }

    public function execute() {
        global $CFG;

        $workdir = make_upload_directory('local_ollamachat/embeddings');
        $outputfile = $workdir . DIRECTORY_SEPARATOR . 'embeddings.json';
        $python_script =  dirname(__DIR__, 2) . '/scripts/generate_embeddings.py';
        $knowledge_url = get_config('local_ollamachat', 'knowledge_api_url');

        $command = sprintf(
            'python3 %s %s %s',
            escapeshellarg($python_script),
            escapeshellarg($knowledge_url),
            escapeshellarg($outputfile)
        );


        $output = shell_exec($command . ' 2>&1');

        if ($output === null || trim($output) === '') {
            mtrace("generate_embeddings.py failed or returned no output.");
        } else {
            mtrace("generate_embeddings.py output: " . $output);
        }
    }
}
