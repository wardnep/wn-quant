@servers(['prod' => ['wardnep@wn']])

@task('deploy', ['on' => 'prod'])
	cd /var/www/wn-quant
	git pull
@endtask
