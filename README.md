===================

Python script for zendesk helpcenter synchronisation.

## Requirements

1. Python 3.+
2. [Zendesk](www.zendesk.com) Account

## Installation

Clone this repo locally, then:

`python setup.py install`

## Usage

Type `zendesk-help-cms -h` and `zendesk-help-cms [command] -h` to see help message in the console.

### Configuration

In the directory you want to have your Zendesk articles type `zendesk-help-cms config`. You will be ask for information required by the script. the information will be saved in `zendesk-help-cms.config` file. If you need to override some values just run `zendesk-help-cms config` again. If the file exists it will offer existing values as defaults. You can also manually create/override values in the file if you wish to do so but make sure the syntax is correct.

The current working directory is used as the root for the script. This means the categories will be created at that level.

#### Zendesk authentication

There are two ways to authenticate with Zendesk. Either with user/password or with user/token. 

For user/password the configuration is straightforward. Just provide the values in the configuration file.

For user/token the configuration is similar but the user email has to end with `/token`. The password is the Zendesk token.

### Importing existing articles

If you already have some articles in Zendesk you can import them with `zendesk-help-cms import` command.

It is possible to create the initial setup by hand but we recommend creating a sample article in Zendesk (if there are no articles there yet) and using the `import` command 

This will create a directory structure similar to the one below:

```
category/
	__group__.json
	.group.meta
	section/
		__group__.json
		.group.meta
			article-title/
				README.md
				__article__.json
				.article.meta
				attachments/
					attachment-one.png
					.attachment-one.png.meta
```

### Uploading translations to Zendesk

To upload content to Zendesk run

`zendesk-help-cms export`

This will upload the **entire** structure to Zendesk updating whatever is already there if it changed (this is checked by comparing md5 hashes of the title and body/description)

## Structure

Going back to our sample folder structure:

```
category/
	__group__.json
	.group.meta
	section/
		__group__.json
		.group.meta
			article-title/
				README.md
				__article__.json
				.article.meta
				attachments/
					attachment-one.png
					.attachment-one.png.meta
```

There are 3 kinds of objects: categories, sections, articles and attachments.

### Categories

A category is a top level group, it holds sections. Each category had a `__group__.json` file containing it's name and description. It is strongly recommended the name reflects the folder name for the default language unless there is some kind of encoding problem or something similar.

```
{
    "description": "testing category",
    "name": "test category"
}
```

The file needs to be created when you add a new category, either by hand or by running `zendesk-help-cms doctor`.

Once a category is in Zendesk help centre it will also have `.group.meta` file containing the information from Zendesk. This file should not be edited and is for internal use only.

### Sections

A sections is very similar to category except it holds articles. Everything else is the same.

### Articles

Each article has a separate folder with a slugified directory name. This folder contains the article body in the markdown file `README.md`, plus the article title in `__article__.json`.

Once an article is in Zendesk it will also have a meta file. This file stores information from Zendesk and is for internal use by the script.

### Attachments

Attachments for an article are placed in the attachments directory under the article directory. Attachments may not be larger than 20MB.

Attachments can be referenced as links/in-line images in the article body `README.md` with the regular markdown in-line syntax, i.e. an image can be added with `![Alt text](/attachments/attachment-one.png)` or as a link `[Link text](/attachments/attachment-two.png)`. The location will be automatically updated with the URL of the attachment in zendesk after it has been uploaded.

If an attachment in the attachments folder is updated after initial upload, this will also be reflected upon next export.

Once an attachment is in Zendesk it will also have a meta file. This file stores information from Zendesk and is for internal use by the script.