//make the sentence correspond with 'logActionsList_extract.js' for i18n
var _ = require('js/rdmGettext')._;
var project_created = _('${user} created ${node}');
var project_registered = _('${user} registered ${node}');
var project_registered_no_user = _('${node} registered');
var prereg_registration_initiated = _('${user} submitted for review to the Preregistration Challenge a registration of ${node}');
var project_deleted = _('${user} deleted ${node}');
var created_from = _('${user} created ${node} based on ${template}');
var pointer_created = _('${user} created a link to ${pointer_category} ${pointer}');
var pointer_forked = _('${user} forked a link to ${pointer_category} ${pointer}');
var pointer_removed = _('${user} removed a link to ${pointer_category} ${pointer}');
var group_added = _('${user} added ${group} to ${node}');
var group_removed = _('${user} removed ${group} from ${node}');
var group_updated = _('${user} changed ${group} permissions to ${node}');
var made_public = _('${user} made ${node} public');
var made_public_no_user = _('${node} made public');
var made_private = _('${user} made ${node} private');
var tag_added = _('${user} added tag ${tag} to ${node}');
var tag_removed = _('${user} removed tag ${tag} from ${node}');
var edit_title = _('${user} changed the title from ${title_original} to ${title_new}');
var edit_description = _('${user} edited description of ${node}');
var category_updated = _('${user} changed the category of ${node}');
var article_doi_updated = _('${user} changed the article_doi of ${node}');
var updated_fields = _('${user} changed the ${updated_fields} for ${node}');
var external_ids_added = _('${user} created external identifier(s) ${identifiers} on ${node}');
var custom_citation_added = _('${user} created a custom citation for ${node}');
var custom_citation_edited = _('${user} edited a custom citation for ${node}');
var custom_citation_removed = _('${user} removed a custom citation from ${node}');
var contributor_added = _('${user} added ${contributors} as contributor(s) to ${node}');
var contributor_removed = _('${user} removed ${contributors} as contributor(s) from ${node}');
var contributors_reordered = _('${user} reordered contributors for ${node}');
var permissions_updated = _('${user} changed permissions for ${node}');
var made_contributor_visible = _('${user} made non-bibliographic contributor ${contributors} a bibliographic contributor on ${node}');
var made_contributor_invisible = _('${user} made bibliographic contributor ${contributors} a non-bibliographic contributor on ${node}');
var wiki_updated = _('${user} updated wiki page ${page} to version ${version} of ${node}');
var wiki_deleted = _('${user} deleted wiki page ${page} of ${node}');
var wiki_renamed = _('${user} renamed wiki page ${old_page} to ${page} of ${node}');
var made_wiki_public = _('${user} made the wiki of ${node} publicly editable');
var made_wiki_private = _('${user} made the wiki of ${node} privately editable');
var addon_added = _('${user} added addon ${addon} to ${node}');
var addon_removed = _('${user} removed addon ${addon} from ${node}');
var addon_file_moved = _('${user} moved ${source} to ${destination} in ${node}');
var addon_file_copied = _('${user} copied ${source} to ${destination} in ${node}');
var addon_file_renamed = _('${user} renamed ${source} to ${destination} in ${node}');
var folder_created = _('${user} created a folder in ${node}');
var file_added = _('${user} added file ${path} to ${node}');
var file_updated = _('${user} updated file in ${node}');
var file_removed = _('${user} removed ${path_type} ${path} from ${node}');
var file_restored = _('${user} restored file ${path} from ${node}');
var file_metadata_updated = _('${user} updated the file metadata for ${path}');
var checked_out = _('${user} checked out ${kind} ${path} from ${node}');
var checked_in = _('${user} checked in ${kind} ${path} to ${node}');
var comment_added = _('${user} added a comment ${comment_location} in ${node}');
var comment_removed = _('${user} deleted a comment ${comment_location} in ${node}');
var comment_restored = _('${user} restored a comment ${comment_location}  in ${node}');
var comment_updated = _('${user} updated a comment ${comment_location} in ${node}');
var embargo_initiated = _('${user} initiated an embargoed registration of ${node}');
var embargo_approved = _('${user} approved embargoed registration of ${node}');
var embargo_approved_no_user = _('Embargo of registration of ${node} approved');
var embargo_cancelled = _('${user} cancelled embargoed registration of ${node}');
var embargo_completed = _('${user} completed embargo of ${node}');
var embargo_completed_no_user = _('Embargo for ${node} completed');
var embargo_terminated = _('Embargo for ${node} ended');
var retraction_initiated = _('${user} initiated withdrawal of a registration of ${node}');
var retraction_initiated_no_user = _('A withdrawal of a registration of ${node} was proposed');
var retraction_approved = _('${user} approved a withdrawal of a registration of ${node}');
var retraction_approved_no_user = _('A withdrawal of a registration of ${node} was approved');
var retraction_cancelled = _('${user} cancelled withdrawal of a registration of ${node}');
var external_registration_created = _('A registration of ${node} was created on an external registry.');
var external_registration_imported = _('A registration of ${node} was imported to OSF from an external registry.');
var registration_initiated = _('${user} initiated a registration of ${node}');
var registration_approved = _('${user} approved a registration of ${node}');
var registration_approved_no_user = _('Registration of ${node} was approved');
var registration_cancelled = _('${user} cancelled a registration of ${node}');
var node_created = _('${user} created ${node}');
var node_forked = _('${user} created fork from ${forked_from}');
var node_removed = _('${user} removed ${node}');
var node_access_requests_enabled = _('${user} enabled access requests for ${node}');
var node_access_requests_disabled = _('${user} disabled access requests for ${node}');
var license_changed = _('${user} updated the license of ${node} ${license}');
var file_tag_added = _('${user} added tag ${tag} to ${path} in ${storage_name} in ${node}');
var file_tag_removed = _('${user} removed tag ${tag} from ${path} in ${storage_name} in ${node}');
var osf_storage_file_added = _('${user} added file ${path} to ${storage_name} in ${node}');
var osf_storage_folder_created = _('${user} created folder ${path} in ${storage_name} in ${node}');
var osf_storage_file_updated = _('${user} updated file ${path} in ${storage_name} in ${node}');
var osf_storage_file_removed = _('${user} removed ${path_type} ${path} from ${storage_name} in ${node}');
var affiliated_institution_added = _('${user} added ${institution} affiliation to ${node}');
var affiliated_institution_removed = _('${user} removed ${institution} affiliation from ${node}');
var preprint_initiated = _('${user} made ${node} a ${preprint} on ${preprint_provider} Preprints');
var preprint_file_updated = _('${user} updated the primary file of this ${preprint} on ${preprint_provider} Preprints');
var preprint_license_updated = _('${user} updated the license of this ${preprint} on ${preprint_provider} Preprints ${license}');
var subjects_updated = _('${user} updated the subjects on ${node}');
var view_only_link_added = _('${user} created ${anonymous_link} view-only link to ${node}');
var view_only_link_removed = _('${user} removed ${anonymous_link} view-only link to ${node}');
var has_coi_updated = _('${user} changed the conflict of interest statement availability for ${preprint}.');
var coi_statement_updated = _('${user} changed the conflict of interest statement for ${preprint}.');
var has_data_links_updated = _('${user} has updated the has links to data field to ${value}');
var data_links_updated = _('${user} has updated their data links');
var why_no_data_updated = _('${user} has updated their data statement');
var has_prereg_links_updated = _('${user} has updated their preregistration data link availability to ${value}');
var prereg_links_updated = _('${user} has updated their preregistration data links');
var why_no_prereg_updated = _('${user} has updated their preregistration data availability statement');
var prereg_links_info_updated = _('${user} has updated their preregistration links to ${value}');
var timestamp_all_verified = _('${user} verified timestamp');
var timestamp_all_added = _('${user} requested trusted timestamp');
var timestamp_added = _('${user} requested trusted timestamp file ${path}');
var timestamp_errors_downloaded = _('${user} downloaded a file of timestamp errors as a ${timestamp_errors_file_format}');
var mapcore_map_group_not_created = _('[MAPCORE_SYNC:ERROR] ${user} cannot create a new mAP group for GRDM project <${node}> (See logs for details)');
var mapcore_map_group_not_updated = _('[MAPCORE_SYNC:ERROR] mAP group for GRDM project <${node}> cannot be updated (See logs for details)');
var mapcore_rdm_project_not_updated = _('[MAPCORE_SYNC:ERROR] GRDM project <${node}> cannot be updated with mAP group (See logs for details)');
var mapcore_rdm_unknown_user = _('[MAPCORE_SYNC:NOTICE] Unknown (unregistered in GRDM) users belong to mAP group <${node}> (ignored) (See logs for details)');
var box_file_added = _('${user} added file ${path} to Box in ${node}');
var box_file_removed = _('${user} removed ${path_type} ${path} from Box in ${node}');
var box_file_updated = _('${user} updated file ${path} in Box in ${node}');
var box_folder_created = _('${user} created folder ${path} in Box in ${node}');
var box_folder_selected = _('${user} linked Box folder ${box_folder} to ${node}');
var box_node_authorized = _('${user} authorized the Box addon in ${node}');
var box_node_deauthorized = _('${user} deauthorized the Box addon for ${node}');
var box_node_deauthorized_no_user = _('Box addon for ${node} deauthorized');
var dataverse_file_added = _('${user} added file ${filename} to Dataverse dataset ${dataset} in ${node}');
var dataverse_file_removed = _('${user} removed file ${filename} from Dataverse dataset ${dataset} in ${node}');
var dataverse_dataset_linked = _('${user} linked Dataverse dataset ${dataset} to ${node}');
var dataverse_study_linked = _('${user} linked Dataverse dataset ${study} to ${node}');
var dataverse_dataset_published = _('${user} published a new version of Dataverse dataset ${dataset} on ${node}');
var dataverse_study_released = _('${user} published a new version of Dataverse dataset ${study} to ${node}');
var dataverse_node_authorized = _('${user} authorized the Dataverse addon for ${node}');
var dataverse_node_deauthorized = _('${user} deauthorized the Dataverse addon for ${node}');
var dataverse_node_deauthorized_no_user = _('Dataverse addon for ${node} deauthorized');
var dropbox_file_added = _('${user} added file ${path} to Dropbox in ${node}');
var dropbox_file_removed = _('${user} removed ${path_type} ${path} from Dropbox in ${node}');
var dropbox_file_updated = _('${user} updated file ${path} in Dropbox in ${node}');
var dropbox_folder_created = _('${user} created folder ${path} in Dropbox in ${node}');
var dropbox_folder_selected = _('${user} linked Dropbox folder ${dropbox_folder} to ${node}');
var dropbox_node_authorized = _('${user} authorized the Dropbox addon for ${node}');
var dropbox_node_deauthorized = _('${user} deauthorized the Dropbox addon for ${node}');
var dropbox_node_deauthorized_no_user = _('Dropbox addon for ${node} deauthorized');
var figshare_folder_selected = _('${user} linked figshare ${folder} ${folder_name} to ${node}');
var figshare_content_unlinked = _('${user} unlinked content from figshare in ${node}');
var figshare_file_added = _('${user} added file ${path} to figshare in ${node}');
var figshare_file_removed = _('${user} removed ${path_type} ${path} from figshare in ${node}');
var figshare_folder_created = _('${user} created folder ${path} in figshare in ${node}');
var figshare_node_authorized = _('${user} authorized the figshare addon for ${node}');
var figshare_node_deauthorized = _('${user} deauthorized the figshare addon for ${node}');
var figshare_node_deauthorized_no_user = _('figshare addon for ${node} deauthorized');
var forward_url_changed = _('${user} changed external link to ${forward_url} in ${node}');
var github_file_added = _('${user} added file ${path} to GitHub repo ${repo} in ${node}');
var github_file_removed = _('${user} removed ${path_type} ${path} in GitHub repo ${repo} in ${node}');
var github_file_updated = _('${user} updated file ${path} in GitHub repo ${repo} in ${node}');
var github_folder_created = _('${user} created folder ${path} in GitHub repo ${repo} in ${node}');
var github_node_authorized = _('${user} authorized the GitHub addon for ${node}');
var github_node_deauthorized = _('${user} deauthorized the GitHub addon for ${node}');
var github_node_deauthorized_no_user = _('GitHub addon for ${node} deauthorized');
var github_repo_linked = _('${user} linked GitHub repo ${repo} to ${node}');
var gitlab_file_added = _('${user} added file ${path} to GitLab repo ${gitlab_repo} in ${node}');
var gitlab_file_removed = _('${user} removed file ${path} in GitLab repo ${gitlab_repo} in ${node}');
var gitlab_file_updated = _('${user} updated file ${path} in GitLab repo ${gitlab_repo} in ${node}');
var gitlab_folder_created = _('${user} created folder ${path} in GitLab repo ${gitlab_repo} in ${node}');
var gitlab_node_authorized = _('${user} authorized the GitLab addon for ${node}');
var gitlab_node_deauthorized = _('${user} deauthorized the GitLab addon for ${node}');
var gitlab_node_deauthorized_no_user = _('GitLab addon for ${node} deauthorized');
var gitlab_repo_linked = _('${user} linked GitLab repo ${gitlab_repo} to ${node}');
var mendeley_folder_selected = _('${user} linked Mendeley folder ${folder_name} to ${node}');
var mendeley_node_authorized = _('${user} authorized the Mendeley addon for ${node}');
var mendeley_node_deauthorized = _('${user} deauthorized the Mendeley addon for ${node}');
var zotero_folder_selected = _('${user} linked Zotero folder ${folder_name} to ${node}');
var zotero_library_selected = _('${user} linked Zotero library ${library_name} to ${node}');
var zotero_node_authorized = _('${user} authorized the Zotero addon for ${node}');
var zotero_node_deauthorized = _('${user} deauthorized the Zotero addon for ${node}');
var owncloud_file_added = _('${user} added file ${path} to ownCloud in ${node}');
var owncloud_file_removed = _('${user} removed ${path_type} ${path} from ownCloud in ${node}');
var owncloud_file_updated = _('${user} updated file ${path} in ownCloud in ${node}');
var owncloud_folder_created = _('${user} created folder ${path} in ownCloud in ${node}');
var owncloud_folder_selected = _('${user} linked ownCloud folder ${folder} to ${node}');
var owncloud_node_authorized = _('${user} authorized the ownCloud addon for ${node}');
var owncloud_node_deauthorized = _('${user} deauthorized the ownCloud addon for ${node}');
var owncloud_node_deauthorized_no_user = _('ownCloud addon for ${node} deauthorized');
var onedrive_file_added = _('${user} added file ${path} to Microsoft OneDrive in ${node}');
var onedrive_file_removed = _('${user} removed ${path_type} ${path} from Microsoft OneDrive in ${node}');
var onedrive_file_updated = _('${user} updated file ${path} in Microsoft OneDrive in ${node}');
var onedrive_folder_created = _('${user} created folder ${path} in Microsoft OneDrive in ${node}');
var onedrive_folder_selected = _('${user} linked Microsoft OneDrive folder ${onedrive_folder} to ${node}');
var onedrive_node_authorized = _('${user} authorized the Microsoft OneDrive addon for ${node}');
var onedrive_node_deauthorized = _('${user} deauthorized the Microsoft OneDrive addon for ${node}');
var onedrive_node_deauthorized_no_user = _('Microsoft OneDrive addon for ${node} deauthorized');
var s3_bucket_linked = _('${user} linked the Amazon S3 bucket ${bucket} to ${node}');
var s3_bucket_unlinked = _('${user} unselected the Amazon S3 bucket ${bucket} in ${node}');
var s3_file_added = _('${user} added file ${path} to Amazon S3 bucket ${bucket} in ${node}');
var s3_file_removed = _('${user} removed ${path} in Amazon S3 bucket ${bucket} in ${node}');
var s3_file_updated = _('${user} updated file ${path} in Amazon S3 bucket ${bucket} in ${node}');
var s3_folder_created = _('${user} created folder ${path} in Amazon S3 bucket ${bucket} in ${node}');
var s3_node_authorized = _('${user} authorized the Amazon S3 addon for ${node}');
var s3_node_deauthorized = _('${user} deauthorized the Amazon S3 addon for ${node}');
var s3_node_deauthorized_no_user = _('Amazon S3 addon for ${node} deauthorized');
var googledrive_file_added = _('${user} added file ${googledrive_path} to Google Drive in ${node}');
var googledrive_file_removed = _('${user} removed ${path_type} ${googledrive_path} from Google Drive in ${node}');
var googledrive_file_updated = _('${user} updated file ${googledrive_path} in Google Drive in ${node}');
var googledrive_folder_created = _('${user} created folder ${googledrive_path} in Google Drive in ${node}');
var googledrive_folder_selected = _('${user} linked Google Drive folder ${googledrive_folder} to ${node}');
var googledrive_node_authorized = _('${user} authorized the Google Drive addon for ${node}');
var googledrive_node_deauthorized = _('${user} deauthorized the Google Drive addon for ${node}');
var googledrive_node_deauthorized_no_user = _('Google Drive addon for ${node} deauthorized');
var bitbucket_file_added = _('${user} added file ${path} to Bitbucket repo ${bitbucket_repo} in ${node}');
var bitbucket_file_removed = _('${user} removed ${path_type} ${path} in Bitbucket repo ${bitbucket_repo} in ${node}');
var bitbucket_file_updated = _('${user} updated file ${path} in Bitbucket repo ${bitbucket_repo} in ${node}');
var bitbucket_folder_created = _('${user} created folder ${path} in Bitbucket repo ${bitbucket_repo} in ${node}');
var bitbucket_node_authorized = _('${user} authorized the Bitbucket addon for ${node}');
var bitbucket_node_deauthorized = _('${user} deauthorized the Bitbucket addon for ${node}');
var bitbucket_node_deauthorized_no_user = _('Bitbucket addon for ${node} deauthorized');
var bitbucket_repo_linked = _('${user} linked Bitbucket repo ${bitbucket_repo} to ${node}');
var swift_bucket_linked = _('${user} linked the Swift container ${bucket} to ${node}');
var swift_bucket_unlinked = _('${user} unselected the Swift container ${bucket} in ${node}');
var swift_file_added = _('${user} added file ${path} to Swift container ${bucket} in ${node}');
var swift_file_removed = _('${user} removed ${path} in Swift container ${bucket} in ${node}');
var swift_file_updated = _('${user} updated file ${path} in Swift container ${bucket} in ${node}');
var swift_folder_created = _('${user} created folder ${path} in Swift container ${bucket} in ${node}');
var swift_node_authorized = _('${user} authorized the Swift addon for ${node}');
var swift_node_deauthorized = _('${user} deauthorized the Swift addon for ${node}');
var swift_node_deauthorized_no_user = _('Swift addon for ${node} deauthorized');
var azureblobstorage_bucket_linked = _('${user} linked the Azure Blob Storage container ${bucket} to ${node}');
var azureblobstorage_bucket_unlinked = _('${user} unselected the Azure Blob Storage container ${bucket} in ${node}');
var azureblobstorage_file_added = _('${user} added file ${path} to Azure Blob Storage container ${bucket} in ${node}');
var azureblobstorage_file_removed = _('${user} removed ${path} in Azure Blob Storage container ${bucket} in ${node}');
var azureblobstorage_file_updated = _('${user} updated file ${path} in Azure Blob Storage container ${bucket} in ${node}');
var azureblobstorage_folder_created = _('${user} created folder ${path} in Azure Blob Storage container ${bucket} in ${node}');
var azureblobstorage_node_authorized = _('${user} authorized the Azure Blob Storage addon for ${node}');
var azureblobstorage_node_deauthorized = _('${user} deauthorized the Azure Blob Storage addon for ${node}');
var azureblobstorage_node_deauthorized_no_user = _('Azure Blob Storage addon for ${node} deauthorized');
var weko_file_added = _('${user} added file ${filename} to WEKO index ${dataset} in ${node}');
var weko_file_removed = _('${user} removed file ${filename} from WEKO index ${dataset} in ${node}');
var weko_index_linked = _('${user} linked WEKO index ${dataset} to ${node}');
var weko_index_created = _('${user} created an index ${filename} on ${node}');
var weko_item_created = _('${user} created an item ${filename} on ${node}');
var weko_folder_created = _('${user} created folder ${filename} in WEKO index ${dataset} in ${node}');
var weko_node_authorized = _('${user} authorized the WEKO addon for ${node}');
var weko_node_deauthorized = _('${user} deauthorized the WEKO addon for ${node}');
var weko_node_deauthorized_no_user = _('WEKO addon for ${node} deauthorized');
var s3compat_bucket_linked = _('${user} linked the S3 Compatible Storage bucket ${bucket} to ${node}');
var s3compat_bucket_unlinked = _('${user} unselected the S3 Compatible Storage bucket ${bucket} in ${node}');
var s3compat_file_added = _('${user} added file ${path} to S3 Compatible Storage bucket ${bucket} in ${node}');
var s3compat_file_removed = _('${user} removed ${path} in S3 Compatible Storage bucket ${bucket} in ${node}');
var s3compat_file_updated = _('${user} updated file ${path} in S3 Compatible Storage bucket ${bucket} in ${node}');
var s3compat_folder_created = _('${user} created folder ${path} in S3 Compatible Storage bucket ${bucket} in ${node}');
var s3compat_node_authorized = _('${user} authorized the S3 Compatible Storage addon for ${node}');
var s3compat_node_deauthorized = _('${user} deauthorized the S3 Compatible Storage addon for ${node}');
var s3compat_node_deauthorized_no_user = _('S3 Compatible Storage addon for ${node} deauthorized');
var s3compatinstitutions_file_added = _('${user} added file ${path} to S3 Compatible Storage for Institutions in ${node}');
var s3compatinstitutions_file_removed = _('${user} removed ${path_type} ${path} from S3 Compatible Storage for Institutions in ${node}');
var s3compatinstitutions_file_updated = _('${user} updated file ${path} in S3 Compatible Storage for Institutions in ${node}');
var s3compatinstitutions_folder_created = _('${user} created folder ${path} in S3 Compatible Storage for Institutions in ${node}');
var s3compatinstitutions_folder_selected = _('${user} linked S3 Compatible Storage for Institutions folder ${folder} to ${node}');
var s3compatinstitutions_node_authorized = _('${user} authorized the S3 Compatible Storage for Institutions addon for ${node}');
var s3compatinstitutions_node_deauthorized = _('${user} deauthorized the S3 Compatible Storage for Institutions addon for ${node}');
var s3compatinstitutions_node_deauthorized_no_user = _('S3 Compatible Storage for Institutions addon for ${node} deauthorized');
var s3compatb3_bucket_linked = _('${user} linked the Oracle Cloud Infrastructure Object Storage bucket ${bucket} to ${node}');
var s3compatb3_bucket_unlinked = _('${user} unselected the Oracle Cloud Infrastructure Object Storage bucket ${bucket} in ${node}');
var s3compatb3_file_added = _('${user} added file ${path} to Oracle Cloud Infrastructure Object Storage bucket ${bucket} in ${node}');
var s3compatb3_file_removed = _('${user} removed ${path} in Oracle Cloud Infrastructure Object Storage bucket ${bucket} in ${node}');
var s3compatb3_file_updated = _('${user} updated file ${path} in Oracle Cloud Infrastructure Object Storage bucket ${bucket} in ${node}');
var s3compatb3_folder_created = _('${user} created folder ${path} in Oracle Cloud Infrastructure Object Storage bucket ${bucket} in ${node}');
var s3compatb3_node_authorized = _('${user} authorized the Oracle Cloud Infrastructure Object Storage addon for ${node}');
var s3compatb3_node_deauthorized = _('${user} deauthorized the Oracle Cloud Infrastructure Object Storage addon for ${node}');
var s3compatb3_node_deauthorized_no_user = _('Oracle Cloud Infrastructure Object Storage addon for ${node} deauthorized');
var ociinstitutions_file_added = _('${user} added file ${path} to Oracle Cloud Infrastructure for Institutions in ${node}');
var ociinstitutions_file_removed = _('${user} removed ${path_type} ${path} from Oracle Cloud Infrastructure for Institutions in ${node}');
var ociinstitutions_file_updated = _('${user} updated file ${path} in Oracle Cloud Infrastructure for Institutions in ${node}');
var ociinstitutions_folder_created = _('${user} created folder ${path} in Oracle Cloud Infrastructure for Institutions in ${node}');
var ociinstitutions_folder_selected = _('${user} linked Oracle Cloud Infrastructure for Institutions folder ${folder} to ${node}');
var ociinstitutions_node_authorized = _('${user} authorized the Oracle Cloud Infrastructure for Institutions addon for ${node}');
var ociinstitutions_node_deauthorized = _('${user} deauthorized the Oracle Cloud Infrastructure for Institutions addon for ${node}');
var ociinstitutions_node_deauthorized_no_user = _('Oracle Cloud Infrastructure for Institutions addon for ${node} deauthorized');
var nextcloud_file_added = _('${user} added file ${path} to Nextcloud in ${node}');
var nextcloud_file_removed = _('${user} removed ${path_type} ${path} from Nextcloud in ${node}');
var nextcloud_file_updated = _('${user} updated file ${path} in Nextcloud in ${node}');
var nextcloud_folder_created = _('${user} created folder ${path} in Nextcloud in ${node}');
var nextcloud_folder_selected = _('${user} linked Nextcloud folder ${folder} to ${node}');
var nextcloud_node_authorized = _('${user} authorized the Nextcloud addon for ${node}');
var nextcloud_node_deauthorized = _('${user} deauthorized the Nextcloud addon for ${node}');
var nextcloud_node_deauthorized_no_user = _('Nextcloud addon for ${node} deauthorized');
var nextcloudinstitutions_file_added = _('${user} added file ${path} to Nextcloud (for Institutions) in ${node}');
var nextcloudinstitutions_file_removed = _('${user} removed ${path_type} ${path} from Nextcloud (for Institutions) in ${node}');
var nextcloudinstitutions_file_updated = _('${user} updated file ${path} in Nextcloud (for Institutions) in ${node}');
var nextcloudinstitutions_folder_created = _('${user} created folder ${path} in Nextcloud (for Institutions) in ${node}');
var nextcloudinstitutions_folder_selected = _('${user} linked Nextcloud (for Institutions) folder ${folder} to ${node}');
var nextcloudinstitutions_node_authorized = _('${user} authorized the Nextcloud (for Institutions) addon for ${node}');
var nextcloudinstitutions_node_deauthorized = _('${user} deauthorized the Nextcloud (for Institutions) addon for ${node}');
var nextcloudinstitutions_node_deauthorized_no_user = _('Nextcloud (for Institutions) addon for ${node} deauthorized');
var iqbrims_file_added = _('${user} added file ${iqbrims_path} to IQB-RIMS in ${node}');
var iqbrims_file_removed = _('${user} removed ${path_type} ${iqbrims_path} from IQB-RIMS in ${node}');
var iqbrims_file_updated = _('${user} updated file ${iqbrims_path} in IQB-RIMS in ${node}');
var iqbrims_folder_created = _('${user} created folder ${iqbrims_path} in IQB-RIMS in ${node}');
var iqbrims_folder_selected = _('${user} linked IQB-RIMS folder ${iqbrims_folder} to ${node}');
var iqbrims_node_authorized = _('${user} authorized the IQB-RIMS addon for ${node}');
var iqbrims_node_deauthorized = _('${user} deauthorized the IQB-RIMS addon for ${node}');
var iqbrims_node_deauthorized_no_user = _('IQB-RIMS addon for ${node} deauthorized');
var iqbrims_imagescan_workflow_start = _('${user} started IQB-RIMS workflow for ${node}');
var iqbrims_imagescan_workflow_finish = _('Finished workflow of ${user} for ${node}');
var iqbrims_paper_workflow_start = _('${user} started IQB-RIMS workflow for ${node}');
var iqbrims_paper_workflow_finish = _('Finished workflow of ${user} for ${node}');
var dropboxbusiness_file_added = _('${user} added file ${path} to Dropbox Business in ${node}');
var dropboxbusiness_file_removed = _('${user} removed ${path_type} ${path} from Dropbox Business in ${node}');
var dropboxbusiness_file_updated = _('${user} updated file ${path} in Dropbox Business in ${node}');
var dropboxbusiness_folder_created = _('${user} created folder ${path} in Dropbox Business in ${node}');
var dropboxbusiness_folder_selected = _('${user} linked Dropbox Business folder ${dropboxbusiness_folder} to ${node}');
var dropboxbusiness_node_authorized = _('${user} authorized the Dropbox Business addon for ${node}');
var dropboxbusiness_node_deauthorized = _('${user} deauthorized the Dropbox Business addon for ${node}');
var dropboxbusiness_node_deauthorized_no_user = _('Dropbox Business addon for ${node} deauthorized');
var onedrivebusiness_file_added = _('${user} added file ${path} to the OneDrive team folder ${folder} in ${node}');
var onedrivebusiness_file_removed = _('${user} removed ${path} in the OneDrive team folder ${folder} in ${node}');
var onedrivebusiness_file_updated = _('${user} updated file ${path} in the OneDrive team folder ${folder} in ${node}');
var onedrivebusiness_folder_created = _('${user} created folder ${path} in the OneDrive team folder ${folder} in ${node}');
var onedrivebusiness_node_authorized = _('${user} authorized the OneDrive for Office365 addon for ${node}');
var onedrivebusiness_node_deauthorized = _('${user} deauthorized the OneDrive for Office365 addon for ${node}');
var onedrivebusiness_node_deauthorized_no_user = _('OneDrive for Office365 addon for ${node} deauthorized');
var metadata_added = _('${user} added metadata in ${node}');
var metadata_file_added = _('${user} added metadata ${path} in ${node}');
var metadata_file_updated = _('${user} updated metadata ${path} in ${node}');
var metadata_file_deleted = _('${user} deleted metadata ${path} in ${node}');
var rushfiles_file_added = _('${user} added file ${rushfiles_path} to Tsukaeru FileBako in ${node}');
var rushfiles_file_removed = _('${user} removed ${path_type} ${rushfiles_path} from Tsukaeru FileBako in ${node}');
var rushfiles_file_updated = _('${user} updated file ${rushfiles_path} in Tsukaeru FileBako in ${node}');
var rushfiles_folder_created = _('${user} created folder ${rushfiles_path} in Tsukaeru FileBako in ${node}');
var rushfiles_folder_selected = _('${user} linked Tsukaeru FileBako folder ${rushfiles_folder} to ${node}');
var rushfiles_node_authorized = _('${user} authorized the Tsukaeru FileBako addon for ${node}');
var rushfiles_node_deauthorized = _('${user} deauthorized the Tsukaeru FileBako addon for ${node}');
var rushfiles_node_deauthorized_no_user = _('Tsukaeru FileBako addon for ${node} deauthorized');
