<?php
// This file is part of Moodle - http://moodle.org/
//
// Moodle is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// Moodle is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with Moodle. If not, see <http://www.gnu.org/licenses/>.

defined('MOODLE_INTERNAL') || die();

if ($hassiteconfig) { // Needs this condition to ensure only site admins can see the settings.
    $settings = new admin_settingpage('local_ollamachat', get_string('pluginname', 'local_ollamachat'));

    $settings->add(new admin_setting_configtext(
        'local_ollamachat/knowledge_api_url',
        get_string('knowledgeurl', 'local_ollamachat'),
        get_string('knowledgeurl_desc', 'local_ollamachat'),
        'https://tusitio.com/api/contenido',
        PARAM_URL
    ));

    // Add the settings page to the local plugins category.
    $ADMIN->add('localplugins', $settings);
}